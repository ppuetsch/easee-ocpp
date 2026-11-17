"""Base class for all entities of a charger, and adding them per charger."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .hub import OcppHub, signal_state_updated
from .models import ChargePointState, Serial
from .server import HUB_DATA_KEY

# Device names get this suffix so they stay apart from the Easee cloud integration's devices
# (and entity ids read e.g. sensor.garage_ocpp_power).
DEVICE_NAME_SUFFIX = " OCPP"


def charger_device_info(hub: OcppHub, serial: Serial) -> DeviceInfo:
    """One device per charger."""
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=f"{hub.config(serial).name}{DEVICE_NAME_SUFFIX}",
        manufacturer=MANUFACTURER,
        serial_number=serial,
    )


def get_hub(hass: HomeAssistant) -> OcppHub | None:
    """Return the hub of the loaded config entry."""
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    return hub


@callback
def async_add_charger_entities(
    hass: HomeAssistant,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entities_for_charger: Callable[[OcppHub, Serial], Iterable[Entity]],
) -> None:
    """Add the entities of every charger to the charger's subentry."""
    hub = get_hub(hass)
    if hub is None:
        return
    for serial in hub.serials():
        async_add_entities(entities_for_charger(hub, serial), config_subentry_id=hub.config(serial).subentry_id)


class OcppEntity(Entity):
    """An entity of one charger that refreshes on every OCPP update."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: OcppHub, serial: Serial, description: EntityDescription) -> None:
        """Bind the entity to one charger."""
        self._hub = hub
        self._serial = serial
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_translation_key = description.translation_key or description.key
        self._attr_device_info = charger_device_info(hub, serial)

    @property
    def charge_point_state(self) -> ChargePointState:
        """Live OCPP state of the charger."""
        return self._hub.state(self._serial)

    @property
    def available(self) -> bool:
        """Values are only meaningful while the charger is connected."""
        return self._hub.is_connected(self._serial)

    async def async_added_to_hass(self) -> None:
        """Follow state changes of the charger."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_state_updated(self._serial), self._handle_state_updated)
        )

    @callback
    def _handle_state_updated(self) -> None:
        self.async_write_ha_state()
