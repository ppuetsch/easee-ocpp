"""Switch chargers back to cloud only when their subentry was deleted."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .cloud import EaseeCloud, EaseeCloudError
from .const import OCPP_VIEW_BASE_PATH
from .models import Serial
from .runtime import EaseeOcppConfigEntry

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "easee_ocpp.chargers"
STORAGE_VERSION = 1


def points_to_home_assistant(url: str | None) -> bool:
    """Return True if the stored OCPP URL is our endpoint (and not another OCPP server)."""
    return url is not None and OCPP_VIEW_BASE_PATH in url


async def async_release_charger(cloud: EaseeCloud, serial: Serial) -> None:
    """Switch a charger whose subentry was removed back to cloud only.

    Otherwise it would keep trying to reach Home Assistant, which no longer accepts it,
    and nobody would answer its RFID requests.
    """
    try:
        connection = await cloud.async_connection(serial)
        if connection.is_enabled() and points_to_home_assistant(connection.url):
            await cloud.async_disable(serial)
    except EaseeCloudError as error:
        _LOGGER.warning("%s: could not switch OCPP off after removal: %s", serial, error.reason)


async def async_release_removed_chargers(
    hass: HomeAssistant, entry: EaseeOcppConfigEntry, configured_serials: set[Serial]
) -> None:
    """Compare with the chargers of the last setup and release the ones that disappeared."""
    store: Store[list[Serial]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    previous_serials = set(await store.async_load() or [])
    for serial in previous_serials - configured_serials:
        entry.async_create_background_task(
            hass, async_release_charger(entry.runtime_data.cloud, serial), f"easee_ocpp_release_{serial}"
        )
    await store.async_save(sorted(configured_serials))
