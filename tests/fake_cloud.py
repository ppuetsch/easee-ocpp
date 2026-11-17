"""Stand-in for the Easee cloud account, so the integration runs without network access."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from custom_components.easee_ocpp.cloud import (
    ChargerReadiness,
    CloudCharger,
    EaseeAuthenticationError,
    EaseeCloudError,
    OcppConnection,
)

type Serial = str

FIRMWARE_WITH_OCPP = 360
VALID_PASSWORD = "cloud-password"


def ready_charger() -> ChargerReadiness:
    """A charger that fulfils every precondition."""
    return ChargerReadiness(
        firmware=FIRMWARE_WITH_OCPP,
        wifi_rssi=-60,
        operator_name="Easee",
        dynamic_circuit_current=(32.0, 32.0, 32.0),
        circuit_max_current=32.0,
    )


@dataclass
class FakeAccount:
    """What the fake cloud knows and what was done to it."""

    chargers: list[CloudCharger] = field(default_factory=list)
    readiness: dict[Serial, ChargerReadiness] = field(default_factory=dict)
    connections: dict[Serial, OcppConnection] = field(default_factory=dict)
    passwords: dict[Serial, str] = field(default_factory=dict)
    lifted_circuits: list[tuple[Serial, float]] = field(default_factory=list)
    forbidden: bool = False
    on_enable: Callable[[Serial, str], None] | None = None


class FakeEaseeCloud:
    """Same interface as EaseeCloud; all instances share one FakeAccount."""

    account = FakeAccount()

    def __init__(self, username: str, password: str) -> None:
        """Remember the password to check it at login."""
        self._password = password

    @classmethod
    def reset(cls, chargers: list[CloudCharger]) -> FakeAccount:
        """Fresh account with these chargers, all ready for OCPP."""
        cls.account = FakeAccount(
            chargers=chargers, readiness={charger.serial: ready_charger() for charger in chargers}
        )
        return cls.account

    async def async_login(self) -> None:
        """Only VALID_PASSWORD works."""
        if self._password != VALID_PASSWORD:
            raise EaseeAuthenticationError

    async def async_chargers(self) -> list[CloudCharger]:
        """Chargers of the account."""
        return self.account.chargers

    async def async_readiness(self, serial: Serial) -> ChargerReadiness:
        """Preconditions of a charger."""
        return self.account.readiness[serial]

    async def async_lift_circuit_limit(self, serial: Serial, amps: float) -> None:
        """Record the request."""
        self.account.lifted_circuits.append((serial, amps))

    async def async_connection(self, serial: Serial) -> OcppConnection:
        """Stored connection."""
        return self.account.connections.get(serial, OcppConnection(mode=None, url=None))

    async def async_enable(self, serial: Serial, url: str, password: str) -> None:
        """Store the connection, or refuse like a user without permission."""
        if self.account.forbidden:
            raise EaseeCloudError("ocpp_forbidden")
        self.account.connections[serial] = OcppConnection(mode="DualProtocol", url=f"{url}/{serial}")
        self.account.passwords[serial] = password
        if self.account.on_enable is not None:
            self.account.on_enable(serial, password)

    async def async_disable(self, serial: Serial) -> None:
        """Switch to cloud only."""
        self.account.connections[serial] = OcppConnection(mode="OcppOff", url=None)
