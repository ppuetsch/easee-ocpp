"""Fix flow of the OCPP repair issues: apply the connection to the charger again."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.selector import TextSelector
import probatio

from .address import normalised_url, suggested_ocpp_url, url_problem
from .cloud import EaseeCloud, EaseeCloudError
from .const import CONF_OCPP_PASSWORD, CONF_OCPP_URL, DOMAIN
from .models import Serial
from .runtime import EaseeOcppConfigEntry


class ReapplyOcppConnectionFlow(RepairsFlow):
    """Lets the user confirm (or correct) the address and re-applies it via the Easee cloud."""

    def __init__(self, serial: Serial) -> None:
        """Repair the connection of this charger."""
        self._serial = serial

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Show the address that will be applied."""
        entry, subentry = self._entry_and_subentry()
        if subentry is None:
            return self.async_abort(reason="charger_not_configured")
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalised_url(user_input[CONF_OCPP_URL])
            problem = url_problem(url)
            if problem is not None:
                errors[CONF_OCPP_URL] = problem
            else:
                try:
                    await self._cloud(entry).async_enable(self._serial, url, subentry.data[CONF_OCPP_PASSWORD])
                except EaseeCloudError as error:
                    errors["base"] = error.reason
                else:
                    self.hass.config_entries.async_update_subentry(
                        entry, subentry, data={**subentry.data, CONF_OCPP_URL: url}
                    )
                    return self.async_create_entry(data={})
        default_url = subentry.data.get(CONF_OCPP_URL) or await suggested_ocpp_url(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema({probatio.Required(CONF_OCPP_URL, default=default_url): TextSelector()}),
            description_placeholders={"serial": self._serial},
            errors=errors,
        )

    def _entry_and_subentry(self) -> tuple[EaseeOcppConfigEntry, ConfigSubentry | None]:
        entry = self.hass.config_entries.async_entries(DOMAIN)[0]
        subentry = next(
            (sub for sub in entry.subentries.values() if sub.unique_id == self._serial),
            None,
        )
        return entry, subentry

    @staticmethod
    def _cloud(entry: EaseeOcppConfigEntry) -> EaseeCloud:
        return entry.runtime_data.cloud
