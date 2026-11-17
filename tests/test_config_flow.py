"""Login flow, options and the charger setup wizard."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee_ocpp.charger_flow import CHECK_FAILED
from custom_components.easee_ocpp.cloud import ChargerReadiness, OcppConnection
from custom_components.easee_ocpp.const import (
    CONF_CHARGER_NAME,
    CONF_OCPP_PASSWORD,
    CONF_OCPP_URL,
    CONF_SERIAL,
    DOMAIN,
    SUBENTRY_TYPE_CHARGER,
)

from .conftest import CLOUD_ONLY_SERIAL, OCPP_SERIAL, ConnectCharger
from .fake_cloud import VALID_PASSWORD, FakeAccount

HA_URL = "ws://192.168.1.10:8123/api/easee_ocpp"
type FlowResult = dict[str, Any]


async def start_wizard(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    """Open the charger wizard."""
    return dict(
        await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_CHARGER), context={"source": SOURCE_USER}
        )
    )


async def submit(hass: HomeAssistant, result: FlowResult, user_input: dict[str, Any] | None = None) -> FlowResult:
    """Submit one wizard step."""
    return dict(await hass.config_entries.subentries.async_configure(result["flow_id"], user_input))


async def until_address(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    """Pick the second charger and pass the precondition step."""
    result = await start_wizard(hass, entry)
    assert result["step_id"] == "user"
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert result["step_id"] == "prerequisites"
    return await submit(hass, result, {})


async def finish_progress(hass: HomeAssistant, result: FlowResult) -> FlowResult:
    """Let the connect task finish and follow the progress-done step."""
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await submit(hass, result)
    # HA follows the progress-done step on its own once the task has finished.
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await submit(hass, result)
    return result


async def test_login_creates_the_account_entry(hass: HomeAssistant) -> None:
    """A wrong password is reported; the right one creates the entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    wrong = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "user@example.com", "password": "wrong"}
    )
    assert wrong["errors"] == {"base": "invalid_auth"}

    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "user@example.com", "password": VALID_PASSWORD}
    )
    assert created["type"] is FlowResultType.CREATE_ENTRY
    assert created["data"] == {"username": "user@example.com", "password": VALID_PASSWORD}


async def test_only_unconfigured_chargers_are_offered(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """The charger that already has a subentry is not in the list."""
    result = await start_wizard(hass, loaded_entry)
    offered = [option["value"] for option in result["data_schema"].schema[CONF_SERIAL].config["options"]]
    assert offered == [CLOUD_ONLY_SERIAL]


async def test_happy_path_switches_the_charger_and_waits_for_it(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger, fake_cloud: FakeAccount
) -> None:
    """The wizard enables OCPP via the cloud, the charger connects, the subentry is created."""

    def charger_connects(serial: str, password: str) -> None:
        asyncio.get_running_loop().create_task(connect_charger(serial, password))

    fake_cloud.on_enable = charger_connects
    result = await until_address(hass, loaded_entry)
    assert result["step_id"] == "address"

    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL + "/"})
    result = await finish_progress(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert fake_cloud.connections[CLOUD_ONLY_SERIAL].url == f"{HA_URL}/{CLOUD_ONLY_SERIAL}"
    subentry = next(sub for sub in loaded_entry.subentries.values() if sub.unique_id == CLOUD_ONLY_SERIAL)
    assert subentry.data[CONF_OCPP_PASSWORD] == fake_cloud.passwords[CLOUD_ONLY_SERIAL]
    assert len(subentry.data[CONF_OCPP_PASSWORD]) == 20
    assert subentry.data[CONF_OCPP_URL] == HA_URL
    assert subentry.data[CONF_CHARGER_NAME] == "Carport"


async def test_timeout_offers_rollback(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount
) -> None:
    """Without connection the user can switch the charger back to cloud only."""
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL})
    result = await finish_progress(hass, result)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "connection_failed"

    result = await submit(hass, result, {"next_step_id": "rollback"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "rolled_back"
    assert fake_cloud.connections[CLOUD_ONLY_SERIAL].mode == "OcppOff"


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("ws://homeassistant.local:8123/api/easee_ocpp", "mdns_host"),
        ("wss://192.168.1.10:8123/api/easee_ocpp", "wss_not_supported"),
        ("http://192.168.1.10:8123/api/easee_ocpp", "invalid_url"),
        ("ws://192.168.1.10:8123/ocpp", "wrong_path"),
    ],
)
async def test_unusable_addresses_are_rejected(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount, url: str, error: str
) -> None:
    """Addresses the charger could not use are explained instead of applied."""
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: url})
    assert result["step_id"] == "address"
    assert result["errors"] == {CONF_OCPP_URL: error}
    assert CLOUD_ONLY_SERIAL not in fake_cloud.connections


async def test_cloud_refusal_returns_to_the_address_step(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount
) -> None:
    """A user without permission sees why instead of waiting ten minutes."""
    fake_cloud.forbidden = True
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "address"
    assert result["errors"] == {"base": "ocpp_forbidden"}


async def test_circuit_limit_can_be_lifted(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount
) -> None:
    """A dynamic circuit limit below the fuse is shown and can be lifted."""
    fake_cloud.readiness[CLOUD_ONLY_SERIAL] = ChargerReadiness(
        firmware=360,
        wifi_rssi=-60,
        operator_name="Easee",
        dynamic_circuit_current=(10.0, 32.0, 32.0),
        circuit_max_current=32.0,
    )
    result = await start_wizard(hass, loaded_entry)
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert "reset_circuit_limit" in result["data_schema"].schema
    assert result["description_placeholders"]["circuit_check"] == CHECK_FAILED

    result = await submit(hass, result, {"reset_circuit_limit": True})

    assert result["step_id"] == "address"
    assert fake_cloud.lifted_circuits == [(CLOUD_ONLY_SERIAL, 32.0)]


async def test_old_firmware_aborts(hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount) -> None:
    """Firmware below 344 cannot do local OCPP."""
    fake_cloud.readiness[CLOUD_ONLY_SERIAL] = ChargerReadiness(
        firmware=300,
        wifi_rssi=-60,
        operator_name="Easee",
        dynamic_circuit_current=(32.0, 32.0, 32.0),
        circuit_max_current=32.0,
    )
    result = await start_wizard(hass, loaded_entry)
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_too_old"


async def test_removing_a_charger_switches_it_back(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount
) -> None:
    """After deletion the charger goes back to cloud only, if it pointed at Home Assistant."""
    fake_cloud.connections[OCPP_SERIAL] = OcppConnection(mode="DualProtocol", url=f"{HA_URL}/{OCPP_SERIAL}")
    subentry_id = next(iter(loaded_entry.subentries))

    hass.config_entries.async_remove_subentry(loaded_entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fake_cloud.connections[OCPP_SERIAL].mode == "OcppOff"


async def test_removal_leaves_foreign_ocpp_servers_alone(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fake_cloud: FakeAccount
) -> None:
    """A charger the user pointed at another OCPP server is not touched."""
    foreign = OcppConnection(mode="DualProtocol", url="ws://other:9000/ocpp")
    fake_cloud.connections[OCPP_SERIAL] = foreign
    subentry_id = next(iter(loaded_entry.subentries))

    hass.config_entries.async_remove_subentry(loaded_entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fake_cloud.connections[OCPP_SERIAL] is foreign
