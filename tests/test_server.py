"""The OCPP endpoint and the hub, with a simulated Easee charger."""

from __future__ import annotations

from typing import Any

from aiohttp import WSServerHandshakeError
from homeassistant.core import Event, HomeAssistant
from ocpp.v16 import call
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee_ocpp.server import HUB_DATA_KEY

from .conftest import ALLOWED_CARD, OCPP_PASSWORD, OCPP_SERIAL, ConnectCharger
from .fake_charger import basic_auth, wait_until


async def bootstrapped(connect_charger: ConnectCharger) -> Any:
    """Connect a charger and wait until the bootstrap requested status and meter values."""
    charger = await connect_charger(OCPP_SERIAL)
    await wait_until(lambda: len(charger.memory.triggered) == 2)
    return charger


async def test_wrong_password_is_refused(loaded_entry: MockConfigEntry, hass_client_no_auth: Any) -> None:
    """A charger with a wrong password gets HTTP 401."""
    client = await hass_client_no_auth()
    with pytest.raises(WSServerHandshakeError) as refused:
        await client.ws_connect(
            f"/api/easee_ocpp/{OCPP_SERIAL}", protocols=("ocpp1.6",), headers=basic_auth(OCPP_SERIAL, "wrong")
        )
    assert refused.value.status == 401


async def test_unknown_charger_is_refused(loaded_entry: MockConfigEntry, hass_client_no_auth: Any) -> None:
    """A serial without subentry gets HTTP 404."""
    client = await hass_client_no_auth()
    with pytest.raises(WSServerHandshakeError) as refused:
        await client.ws_connect(
            "/api/easee_ocpp/EHOTHER", protocols=("ocpp1.6",), headers=basic_auth("EHOTHER", OCPP_PASSWORD)
        )
    assert refused.value.status == 404


async def test_bootstrap_configures_the_charger(hass: HomeAssistant, connect_charger: ConnectCharger) -> None:
    """After connecting, measurands, interval, limit and triggers are set up."""
    charger = await bootstrapped(connect_charger)
    hub = hass.data[HUB_DATA_KEY]

    assert "Energy.Active.Import.Register" in charger.memory.configuration["MeterValuesSampledData"]
    assert hub.state(OCPP_SERIAL).meter_value_sample_interval == 30
    profile = charger.memory.charging_profiles[-1]
    assert profile["charging_profile_purpose"] == "ChargePointMaxProfile"
    assert hub.state(OCPP_SERIAL).composite_limit_amps == 32.0
    assert "FreeCharging" in hub.state(OCPP_SERIAL).unsupported_configuration_keys


async def test_cards_registered_as_tags_are_accepted(hass: HomeAssistant, connect_charger: ConnectCharger) -> None:
    """Only cards that exist as HA tags may charge; every decision fires an event."""
    events: list[Event] = []
    hass.bus.async_listen("easee_ocpp_authorization", events.append)
    scans: list[Event] = []
    hass.bus.async_listen("tag_scanned", scans.append)
    charger = await bootstrapped(connect_charger)

    known = await charger.call(call.Authorize(id_tag=ALLOWED_CARD.lower()))
    unknown = await charger.call(call.Authorize(id_tag="DEADBEEF"))
    await hass.async_block_till_done()

    assert known.id_tag_info["status"] == "Accepted"
    assert unknown.id_tag_info["status"] == "Invalid"
    assert [event.data["accepted"] for event in events] == [True, False]
    assert [scan.data["tag_id"] for scan in scans] == [ALLOWED_CARD]
    assert "DEADBEEF" not in hass.data["tag"].data


async def test_accept_all_cards_option(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger
) -> None:
    """With the option every card is accepted and registered as tag."""
    hass.config_entries.async_update_entry(loaded_entry, options={"accept_all_cards": True})
    await hass.async_block_till_done()
    charger = await bootstrapped(connect_charger)

    answer = await charger.call(call.Authorize(id_tag="NEWCARD1"))
    await hass.async_block_till_done()

    assert answer.id_tag_info["status"] == "Accepted"
    assert "NEWCARD1" in hass.data["tag"].data


async def test_transaction_and_meter_values(hass: HomeAssistant, connect_charger: ConnectCharger) -> None:
    """A session tracks energy from the meter register."""
    charger = await bootstrapped(connect_charger)
    started = await charger.call(
        call.StartTransaction(connector_id=1, id_tag=ALLOWED_CARD, meter_start=1000, timestamp="2026-11-09T10:00:00Z")
    )
    await charger.call(
        call.MeterValues(
            connector_id=1,
            meter_value=[
                {
                    "timestamp": "2026-11-09T10:05:00Z",
                    "sampledValue": [
                        {"value": "1.5", "measurand": "Energy.Active.Import.Register", "unit": "kWh"},
                        {"value": "3.6", "measurand": "Power.Active.Import", "unit": "kW"},
                        {"value": "16.0", "measurand": "Current.Import", "phase": "L1", "unit": "A"},
                    ],
                }
            ],
        )
    )
    state = hass.data[HUB_DATA_KEY].state(OCPP_SERIAL)
    assert state.session_energy_wh() == 500.0
    assert state.measurement("Power.Active.Import") == 3600.0
    assert state.measurement("Current.Import", "L1") == 16.0

    await charger.call(
        call.StopTransaction(meter_stop=1800, timestamp="2026-11-09T10:10:00Z", transaction_id=started.transaction_id)
    )
    assert not state.has_transaction()
    assert state.session_energy_wh() == 800.0


async def test_disconnect_marks_charger_offline(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_client_no_auth: Any
) -> None:
    """Closing the websocket sets connected to False."""
    hub = hass.data[HUB_DATA_KEY]
    client = await hass_client_no_auth()
    websocket = await client.ws_connect(
        f"/api/easee_ocpp/{OCPP_SERIAL}", protocols=("ocpp1.6",), headers=basic_auth(OCPP_SERIAL, OCPP_PASSWORD)
    )
    await wait_until(lambda: hub.is_connected(OCPP_SERIAL))
    await websocket.close()
    await wait_until(lambda: not hub.is_connected(OCPP_SERIAL))
    assert hub.state(OCPP_SERIAL).connected is False
