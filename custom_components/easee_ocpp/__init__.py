"""Easee Local OCPP: Home Assistant as OCPP 1.6J server of Easee chargers."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .authorization import TagAuthorizer
from .cloud import EaseeCloud
from .const import (
    CONF_ACCEPT_ALL_CARDS,
    CONF_CHARGER_NAME,
    CONF_OCPP_PASSWORD,
    CONF_SERIAL,
    DOMAIN,
    SUBENTRY_TYPE_CHARGER,
)
from .health import OcppHealthMonitor
from .hub import OcppChargerConfig, OcppHub
from .removal import async_release_removed_chargers
from .runtime import EaseeOcppConfigEntry, EaseeOcppData
from .server import HUB_DATA_KEY, OcppWebSocketView
from .services import async_setup_ocpp_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the OCPP endpoint and the actions once."""
    hass.http.register_view(OcppWebSocketView())
    async_setup_ocpp_services(hass)
    return True


def charger_configs(entry: EaseeOcppConfigEntry) -> list[OcppChargerConfig]:
    """Return the chargers that have a subentry."""
    return [
        OcppChargerConfig(
            serial=subentry.data[CONF_SERIAL],
            password=subentry.data[CONF_OCPP_PASSWORD],
            name=subentry.data.get(CONF_CHARGER_NAME, subentry.data[CONF_SERIAL]),
            subentry_id=subentry.subentry_id,
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER
    ]


async def async_setup_entry(hass: HomeAssistant, entry: EaseeOcppConfigEntry) -> bool:
    """Start serving the chargers of this account."""
    cloud = EaseeCloud(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    authorizer = TagAuthorizer(hass, entry.options.get(CONF_ACCEPT_ALL_CARDS, False))
    hub = OcppHub(hass, charger_configs(entry), authorizer)
    await hub.async_load()
    hass.data[HUB_DATA_KEY] = hub
    entry.runtime_data = EaseeOcppData(hub=hub, cloud=cloud)
    await async_release_removed_chargers(hass, entry, set(hub.serials()))
    await OcppHealthMonitor(hass, entry, hub).async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: EaseeOcppConfigEntry) -> None:
    """Options or chargers changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EaseeOcppConfigEntry) -> bool:
    """Close all OCPP connections (the chargers reconnect on their own)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.hub.async_shutdown()
    hass.data.pop(HUB_DATA_KEY, None)
    return unloaded
