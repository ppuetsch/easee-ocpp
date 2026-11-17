"""Repair flows: re-apply a charger's OCPP connection via the Easee cloud."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from .health import is_ocpp_issue
from .repair_flow import ReapplyOcppConnectionFlow


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Issues of a charger re-apply its connection; anything else is just confirmed."""
    if is_ocpp_issue(issue_id) and data is not None and "serial" in data:
        return ReapplyOcppConnectionFlow(str(data["serial"]))
    return ConfirmRepairFlow()
