"""What a loaded config entry keeps at runtime."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .cloud import EaseeCloud
from .hub import OcppHub


@dataclass
class EaseeOcppData:
    """The OCPP hub of the chargers and the cloud account used to set them up."""

    hub: OcppHub
    cloud: EaseeCloud


type EaseeOcppConfigEntry = ConfigEntry[EaseeOcppData]
