"""The few Easee cloud calls the integration needs, on top of the generated client.

The cloud is only used to set the charger up: list the chargers of the account, check the
preconditions, and switch the charger's OCPP connection on or off. Everything at runtime
goes through the local OCPP connection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any

from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import get_default_context
import httpx

from .const import EASEE_API_BASE_URL
from .easee_cloud_client import AuthenticatedClient, Client
from .easee_cloud_client.api.account import (
    account_authenticate,
    account_get_charger_favorites,
    account_refresh_token,
)
from .easee_cloud_client.api.charger import (
    charger_get_cached_charger_config,
    charger_get_charger_operator,
    charger_get_charger_site,
)
from .easee_cloud_client.api.direct_ocpp_for_users import (
    apply_ocpp_for_user_charger_endpoint,
    disable_ocpp_for_user_charger_endpoint,
    get_user_charger_connection_details_endpoint,
    post_user_charger_connection_details_endpoint,
)
from .easee_cloud_client.api.observations import getobservations
from .easee_cloud_client.api.site import site_set_dynamic_circuit_current
from .easee_cloud_client.models import (
    AccessControlAPILogin,
    AccessControlAPIRefreshTokenDTO,
    AccessControlAPIUserToken,
    CurrentDeviceStateAPIMultiObservationResponse,
    EaseeCloudAPIChargerConfigurationDTO,
    EaseeCloudAPIDynamicCircuitCurrentTtlDto,
    EaseeCloudAPISiteDTO,
    EaseeOCPPConfigurationAPIApplyOcppForUserChargerRequest,
    EaseeOCPPConfigurationAPIConnectionDetailsDto,
    EaseeOCPPConfigurationAPIConnectivityMode,
    EaseeOCPPConfigurationAPIPostUserChargerConnectionDetailsRequest,
    EaseeOCPPConfigurationAPIPostUserChargerConnectionDetailsResponse,
    EaseeOCPPConfigurationAPIWebsocketConnectionArgs,
)
from .easee_cloud_client.types import UNSET, Response
from .models import Serial

_LOGGER = logging.getLogger(__name__)

MINIMUM_OCPP_FIRMWARE = 344
OPERATOR_EASEE = "Easee"
# Observation ids of the Easee state API (see pyeasee ChargerStreamData).
OBSERVATION_FIRMWARE = 80
OBSERVATION_DYNAMIC_CIRCUIT_CURRENT = (111, 112, 113)
OBSERVATION_WIFI_RSSI = 132
# Renew the access token a minute before it expires.
TOKEN_RENEWAL_MARGIN = timedelta(minutes=1)
SUCCESS_STATUSES = {HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.ACCEPTED, HTTPStatus.NO_CONTENT}


class EaseeCloudError(Exception):
    """The Easee cloud refused or failed; reason is a translation key of the flows."""

    def __init__(self, reason: str) -> None:
        """Remember the reason."""
        super().__init__(reason)
        self.reason = reason


class EaseeAuthenticationError(EaseeCloudError):
    """The credentials were rejected."""

    def __init__(self) -> None:
        """Reason invalid_auth."""
        super().__init__("invalid_auth")


@dataclass(frozen=True)
class CloudCharger:
    """A charger of the account."""

    serial: Serial
    name: str


@dataclass(frozen=True)
class OcppConnection:
    """What the Easee cloud has stored for a charger."""

    mode: str | None
    url: str | None

    def is_enabled(self) -> bool:
        """Return True if the charger connects to an OCPP server."""
        return self.mode == EaseeOCPPConfigurationAPIConnectivityMode.DUALPROTOCOL


@dataclass(frozen=True)
class ChargerReadiness:
    """Preconditions for local OCPP."""

    firmware: int | None
    wifi_rssi: int | None
    operator_name: str | None
    dynamic_circuit_current: tuple[float | None, ...]
    circuit_max_current: float | None

    def firmware_supports_ocpp(self) -> bool:
        """Easee supports local OCPP from firmware 344 on."""
        return self.firmware is not None and self.firmware >= MINIMUM_OCPP_FIRMWARE

    def is_on_wifi(self) -> bool:
        """Over cellular the charger cannot reach Home Assistant."""
        return self.wifi_rssi is not None and self.wifi_rssi != 0

    def operator_is_easee(self) -> bool:
        """Return True if Easee is the operator of the site, which OCPP requires."""
        return self.operator_name in {None, OPERATOR_EASEE}

    def circuit_is_limited(self) -> bool:
        """Return True if a dynamic circuit limit below the fuse caps the OCPP limits."""
        maximum = self.circuit_max_current
        return maximum is not None and any(
            current is not None and current < maximum for current in self.dynamic_circuit_current
        )


@dataclass
class Tokens:
    """Access and refresh token of the account."""

    access_token: str
    refresh_token: str
    expires_at: datetime

    def need_renewal(self) -> bool:
        """Return True shortly before the access token expires."""
        return dt_util.utcnow() >= self.expires_at - TOKEN_RENEWAL_MARGIN


def tokens_from(user_token: AccessControlAPIUserToken | None) -> Tokens:
    """Convert the login answer; a missing token means the login failed."""
    if user_token is None or not isinstance(user_token.access_token, str):
        raise EaseeAuthenticationError
    expires_in = user_token.expires_in if isinstance(user_token.expires_in, int) else 0
    refresh_token = user_token.refresh_token if isinstance(user_token.refresh_token, str) else ""
    return Tokens(user_token.access_token, refresh_token, dt_util.utcnow() + timedelta(seconds=expires_in))


def error_for_status(status: int) -> EaseeCloudError:
    """Translate an HTTP status into a flow error."""
    if status == HTTPStatus.UNAUTHORIZED:
        return EaseeAuthenticationError()
    if status == HTTPStatus.FORBIDDEN:
        return EaseeCloudError("ocpp_forbidden")
    if status == HTTPStatus.BAD_REQUEST:
        return EaseeCloudError("ocpp_rejected")
    return EaseeCloudError("cloud_unavailable")


def parsed_or_raise[T](response: Response[Any], expected: type[T]) -> T:
    """Return the parsed body of a successful response (error bodies are other models)."""
    if response.status_code not in SUCCESS_STATUSES or not isinstance(response.parsed, expected):
        raise error_for_status(response.status_code)
    return response.parsed


def ensure_success(response: Response[Any]) -> None:
    """Raise unless the call succeeded (bodies of these calls are irrelevant)."""
    if response.status_code not in SUCCESS_STATUSES:
        raise error_for_status(response.status_code)


def number_or_none(value: Any) -> float | None:
    """Observation values come as numbers or numeric strings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class EaseeCloud:
    """An Easee account; logs in on demand and renews its token."""

    def __init__(self, username: str, password: str) -> None:
        """Remember the credentials; nothing is sent until the first call."""
        self._username = username
        self._password = password
        self._tokens: Tokens | None = None
        self._ssl_context = get_default_context()

    async def async_login(self) -> None:
        """Log in with the credentials (raises EaseeAuthenticationError if rejected)."""
        body = AccessControlAPILogin(user_name=self._username, password=self._password)
        response = await self._call(lambda: account_authenticate.asyncio_detailed(client=self._anonymous(), body=body))
        if response.status_code in {HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise EaseeAuthenticationError
        self._tokens = tokens_from(parsed_or_raise(response, AccessControlAPIUserToken))

    async def async_chargers(self) -> list[CloudCharger]:
        """All chargers of the account, by site and circuit."""
        client = await self._client()
        sites = parsed_or_raise(
            await self._call(lambda: account_get_charger_favorites.asyncio_detailed(client=client)), list
        )
        return [
            CloudCharger(serial=charger.id, name=str(charger.name or charger.id))
            for site in sites
            for circuit in (site.circuits or [])
            for charger in (circuit.chargers or [])
            if isinstance(charger.id, str)
        ]

    async def async_readiness(self, serial: Serial) -> ChargerReadiness:
        """Firmware, Wi-Fi, operator and circuit limits of a charger."""
        client = await self._client()
        observation_ids = ",".join(
            str(observation)
            for observation in (OBSERVATION_FIRMWARE, OBSERVATION_WIFI_RSSI, *OBSERVATION_DYNAMIC_CIRCUIT_CURRENT)
        )
        observations = parsed_or_raise(
            await self._call(lambda: getobservations.asyncio_detailed(serial, client=client, ids=observation_ids)),
            CurrentDeviceStateAPIMultiObservationResponse,
        )
        values = {observation.id: observation.value for observation in (observations.observations or [])}
        config = parsed_or_raise(
            await self._call(lambda: charger_get_cached_charger_config.asyncio_detailed(serial, client=client)),
            EaseeCloudAPIChargerConfigurationDTO,
        )
        operator = await self._call(lambda: charger_get_charger_operator.asyncio_detailed(serial, client=client))
        operator_name = (
            operator.parsed.name if operator.parsed is not None and isinstance(operator.parsed.name, str) else None
        )
        firmware = number_or_none(values.get(OBSERVATION_FIRMWARE))
        wifi = number_or_none(values.get(OBSERVATION_WIFI_RSSI))
        circuit_maximum = (
            config.circuit_max_current_p1 if isinstance(config.circuit_max_current_p1, float | int) else None
        )
        return ChargerReadiness(
            firmware=int(firmware) if firmware is not None else None,
            wifi_rssi=int(wifi) if wifi is not None else None,
            operator_name=operator_name,
            dynamic_circuit_current=tuple(
                number_or_none(values.get(phase)) for phase in OBSERVATION_DYNAMIC_CIRCUIT_CURRENT
            ),
            circuit_max_current=float(circuit_maximum) if circuit_maximum is not None else None,
        )

    async def async_lift_circuit_limit(self, serial: Serial, amps: float) -> None:
        """Set the dynamic current of the charger's circuit to amps on all phases."""
        client = await self._client()
        site = parsed_or_raise(
            await self._call(lambda: charger_get_charger_site.asyncio_detailed(serial, client=client)),
            EaseeCloudAPISiteDTO,
        )
        circuit = next(
            (
                circuit
                for circuit in (site.circuits or [])
                if any(charger.id == serial for charger in (circuit.chargers or []))
            ),
            None,
        )
        if circuit is None or not isinstance(site.id, int) or not isinstance(circuit.id, int):
            raise EaseeCloudError("cloud_unavailable")
        body = EaseeCloudAPIDynamicCircuitCurrentTtlDto(phase1=amps, phase2=amps, phase3=amps)
        site_id, circuit_id = str(site.id), circuit.id
        ensure_success(
            await self._call(
                lambda: site_set_dynamic_circuit_current.asyncio_detailed(site_id, circuit_id, client=client, body=body)
            )
        )

    async def async_connection(self, serial: Serial) -> OcppConnection:
        """Return the OCPP connection stored for the charger."""
        client = await self._client()
        response = await self._call(
            lambda: get_user_charger_connection_details_endpoint.asyncio_detailed(serial, client=client)
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            return OcppConnection(mode=None, url=None)
        details = parsed_or_raise(response, EaseeOCPPConfigurationAPIConnectionDetailsDto)
        url = details.websocket_connection_args.url if details.websocket_connection_args is not UNSET else None
        return OcppConnection(mode=str(details.connectivity_mode), url=url)

    async def async_enable(self, serial: Serial, url: str, password: str) -> None:
        """Point the charger at url with basic auth (the charger appends /<serial>)."""
        body = EaseeOCPPConfigurationAPIPostUserChargerConnectionDetailsRequest(
            websocket_connection_args=EaseeOCPPConfigurationAPIWebsocketConnectionArgs(url=url),
            connectivity_mode=EaseeOCPPConfigurationAPIConnectivityMode.DUALPROTOCOL,
            basic_auth_password=password,
        )
        client = await self._client()
        stored = parsed_or_raise(
            await self._call(
                lambda: post_user_charger_connection_details_endpoint.asyncio_detailed(serial, client=client, body=body)
            ),
            EaseeOCPPConfigurationAPIPostUserChargerConnectionDetailsResponse,
        )
        apply_request = EaseeOCPPConfigurationAPIApplyOcppForUserChargerRequest(version=stored.version)
        ensure_success(
            await self._call(
                lambda: apply_ocpp_for_user_charger_endpoint.asyncio_detailed(serial, client=client, body=apply_request)
            )
        )
        _LOGGER.info("%s: OCPP enabled via the Easee cloud (%s)", serial, url)

    async def async_disable(self, serial: Serial) -> None:
        """Switch the charger back to cloud only."""
        client = await self._client()
        ensure_success(
            await self._call(lambda: disable_ocpp_for_user_charger_endpoint.asyncio_detailed(serial, client=client))
        )
        _LOGGER.info("%s: OCPP switched off via the Easee cloud", serial)

    def _anonymous(self) -> Client:
        return Client(base_url=EASEE_API_BASE_URL, verify_ssl=self._ssl_context)

    async def _client(self) -> AuthenticatedClient:
        """Return a client with a valid access token (renewed or logged in again as needed)."""
        if self._tokens is None:
            await self.async_login()
        elif self._tokens.need_renewal():
            await self._renew()
        assert self._tokens is not None
        return AuthenticatedClient(
            base_url=EASEE_API_BASE_URL, token=self._tokens.access_token, verify_ssl=self._ssl_context
        )

    async def _renew(self) -> None:
        assert self._tokens is not None
        body = AccessControlAPIRefreshTokenDTO(refresh_token=self._tokens.refresh_token)
        response = await self._call(lambda: account_refresh_token.asyncio_detailed(client=self._anonymous(), body=body))
        if response.status_code in SUCCESS_STATUSES and response.parsed is not None:
            self._tokens = tokens_from(response.parsed)
        else:
            await self.async_login()

    async def _call[T](self, request: Callable[[], Awaitable[Response[T]]]) -> Response[T]:
        """Run a request; network problems become cloud_unavailable."""
        try:
            return await request()
        except (httpx.HTTPError, TimeoutError) as error:
            _LOGGER.warning("Easee cloud not reachable: %s", error)
            raise EaseeCloudError("cloud_unavailable") from error
