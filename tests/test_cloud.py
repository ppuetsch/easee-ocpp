"""The cloud wrapper with the generated client against recorded Easee answers (no network)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from custom_components.easee_ocpp.cloud import EaseeAuthenticationError, EaseeCloud

API = "https://api.easee.com"
SERIAL = "EH000001"
LOGIN_ANSWER = {"accessToken": "token-1", "expiresIn": 86400, "refreshToken": "refresh-1", "tokenType": "Bearer"}


@pytest.fixture
def easee_api():
    """Recorded Easee answers."""
    with respx.mock(base_url=API, assert_all_called=False) as mock:
        mock.post("/api/accounts/login").respond(200, json=LOGIN_ANSWER)
        yield mock


async def test_enable_stores_and_applies_with_empty_apply_answer(easee_api: respx.MockRouter) -> None:
    """Storing answers 201, applying 200 with an empty body (as the real API does)."""
    store = easee_api.post(f"/local-ocpp/v1/connection-details/{SERIAL}").respond(201, json={"version": "v-1"})
    apply = easee_api.post(f"/local-ocpp/v1/connections/chargers/{SERIAL}").respond(200, content=b"")

    await EaseeCloud("user", "password").async_enable(SERIAL, "ws://ha:8123/api/easee_ocpp", "secret")

    stored = json.loads(store.calls.last.request.content)
    assert stored == {
        "websocketConnectionArgs": {"url": "ws://ha:8123/api/easee_ocpp"},
        "connectivityMode": "DualProtocol",
        "basicAuthPassword": "secret",
    }
    assert json.loads(apply.calls.last.request.content) == {"version": "v-1"}
    assert store.calls.last.request.headers["Authorization"] == "Bearer token-1"


async def test_disable_with_empty_answer(easee_api: respx.MockRouter) -> None:
    """Disabling answers 200 with an empty body."""
    disable = easee_api.delete(f"/local-ocpp/v1/connections/chargers/{SERIAL}").respond(200, content=b"")

    await EaseeCloud("user", "password").async_disable(SERIAL)

    assert disable.called


async def test_connection_details(easee_api: respx.MockRouter) -> None:
    """GET connection-details returns mode and URL."""
    easee_api.get(f"/local-ocpp/v1/connection-details/{SERIAL}").respond(
        200,
        json={
            "version": "v-1",
            "connectivityMode": "DualProtocol",
            "websocketConnectionArgs": {"url": f"ws://ha:8123/api/easee_ocpp/{SERIAL}"},
            "basicAuth": None,
        },
    )

    connection = await EaseeCloud("user", "password").async_connection(SERIAL)

    assert connection.is_enabled()
    assert connection.url == f"ws://ha:8123/api/easee_ocpp/{SERIAL}"


async def test_readiness_from_observations(easee_api: respx.MockRouter) -> None:
    """Firmware, Wi-Fi and circuit currents come from the observations API."""
    easee_api.get(f"/state/{SERIAL}/observations").respond(
        200,
        json={
            "observations": [
                {"id": 80, "timestamp": "2026-11-18T05:00:00Z", "dataType": 4, "value": 344},
                {"id": 132, "timestamp": "2026-11-18T05:00:00Z", "dataType": 4, "value": -61},
                {"id": 111, "timestamp": "2026-11-18T05:00:00Z", "dataType": 3, "value": 10.0},
                {"id": 112, "timestamp": "2026-11-18T05:00:00Z", "dataType": 3, "value": 32.0},
                {"id": 113, "timestamp": "2026-11-18T05:00:00Z", "dataType": 3, "value": 32.0},
            ]
        },
    )
    easee_api.get(f"/api/chargers/{SERIAL}/config").respond(200, json={"circuitMaxCurrentP1": 32.0})
    easee_api.get(f"/api/chargers/{SERIAL}/partners").respond(200, json={"id": 20, "name": "Easee"})

    readiness = await EaseeCloud("user", "password").async_readiness(SERIAL)

    assert readiness.firmware_supports_ocpp()
    assert readiness.is_on_wifi()
    assert readiness.operator_is_easee()
    assert readiness.circuit_is_limited()


async def test_wrong_password() -> None:
    """A rejected login raises EaseeAuthenticationError."""
    with respx.mock(base_url=API) as mock:
        mock.post("/api/accounts/login").respond(400, json={"title": "Invalid credentials"})
        with pytest.raises(EaseeAuthenticationError):
            await EaseeCloud("user", "wrong").async_login()


async def test_network_problem_is_reported_as_unavailable() -> None:
    """Connection errors become the flow error cloud_unavailable."""
    with respx.mock(base_url=API) as mock:
        mock.post("/api/accounts/login").mock(side_effect=httpx.ConnectError("offline"))
        with pytest.raises(Exception, match="cloud_unavailable"):
            await EaseeCloud("user", "password").async_login()
