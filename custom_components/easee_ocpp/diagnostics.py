"""Diagnostics: subentries and live state of every charger; secrets and cards redacted."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_OCPP_PASSWORD, SUBENTRY_TYPE_CHARGER
from .models import ChargePointState
from .runtime import EaseeOcppConfigEntry

TO_REDACT = {CONF_OCPP_PASSWORD, CONF_PASSWORD, CONF_USERNAME, "id_tag"}


def state_diagnostics(state: ChargePointState) -> dict[str, Any]:
    """Return the live state as plain data."""
    data = asdict(state)
    data["measurements"] = {
        f"{measurand}/{phase or '-'}": {"value": sample.value, "timestamp": sample.timestamp.isoformat()}
        for (measurand, phase), sample in state.measurements.items()
    }
    data["unsupported_configuration_keys"] = sorted(state.unsupported_configuration_keys)
    return data


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: EaseeOcppConfigEntry) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    hub = entry.runtime_data.hub
    chargers = {
        serial: {"connected": hub.is_connected(serial), "state": state_diagnostics(hub.state(serial))}
        for serial in hub.serials()
    }
    subentries = [
        dict(subentry.data) for subentry in entry.subentries.values() if subentry.subentry_type == SUBENTRY_TYPE_CHARGER
    ]
    return async_redact_data(
        {"account": dict(entry.data), "options": dict(entry.options), "subentries": subentries, "chargers": chargers},
        TO_REDACT,
    )
