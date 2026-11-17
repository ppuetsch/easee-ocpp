"""Button entities: restart, reboot, unlock and refresh."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .charge_point import CommandFailedError
from .entity import OcppEntity, async_add_charger_entities
from .hub import OcppHub
from .models import Serial


async def soft_reset(hub: OcppHub, serial: Serial) -> None:
    """Restart the charger software."""
    await hub.charge_point(serial).reset(hard=False)


async def hard_reset(hub: OcppHub, serial: Serial) -> None:
    """Reboot the charger."""
    await hub.charge_point(serial).reset(hard=True)


async def unlock_connector(hub: OcppHub, serial: Serial) -> None:
    """Release the cable."""
    await hub.charge_point(serial).unlock_connector()


async def refresh(hub: OcppHub, serial: Serial) -> None:
    """Ask for status, meter values, limit and configuration now."""
    await hub.async_refresh(serial)


@dataclass(frozen=True, kw_only=True)
class OcppButtonEntityDescription(ButtonEntityDescription):
    """A button that runs one command."""

    press_fn: Callable[[OcppHub, Serial], Awaitable[None]]


BUTTON_DESCRIPTIONS: tuple[OcppButtonEntityDescription, ...] = (
    OcppButtonEntityDescription(
        key="soft_reset",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=soft_reset,
    ),
    OcppButtonEntityDescription(
        key="hard_reset",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=hard_reset,
    ),
    OcppButtonEntityDescription(key="unlock", press_fn=unlock_connector),
    OcppButtonEntityDescription(
        key="refresh",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=refresh,
    ),
)


class OcppButton(OcppEntity, ButtonEntity):
    """Runs a command on the charger."""

    entity_description: OcppButtonEntityDescription

    async def async_press(self) -> None:
        """Run the command."""
        try:
            await self.entity_description.press_fn(self._hub, self._serial)
        except CommandFailedError as error:
            raise HomeAssistantError(str(error)) from error


def ocpp_buttons(hub: OcppHub, serial: Serial) -> list[OcppButton]:
    """All buttons of one charger."""
    return [OcppButton(hub, serial, description) for description in BUTTON_DESCRIPTIONS]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the platform for all chargers."""
    async_add_charger_entities(hass, async_add_entities, ocpp_buttons)
