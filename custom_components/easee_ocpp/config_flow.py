"""Config flow: log in to the Easee account; chargers are added as subentries (charger_flow)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import BooleanSelector, TextSelector, TextSelectorConfig, TextSelectorType
import probatio

from .charger_flow import OcppChargerSubentryFlow
from .cloud import EaseeCloud, EaseeCloudError
from .const import CONF_ACCEPT_ALL_CARDS, DOMAIN, SUBENTRY_TYPE_CHARGER

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def login_error(username: str, password: str) -> str | None:
    """Try the credentials; return a translation key of the error, or None if they work."""
    try:
        await EaseeCloud(username, password).async_login()
    except EaseeCloudError as error:
        return error.reason
    return None


class EaseeOcppConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in to the Easee account the chargers belong to."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the Easee login."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            error = await login_error(username, user_input[CONF_PASSWORD])
            if error is None:
                return self.async_create_entry(
                    title=username, data={CONF_USERNAME: username, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_USERNAME): TextSelector(), probatio.Required(CONF_PASSWORD): PASSWORD_SELECTOR}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start re-authentication because the stored password no longer works."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await login_error(entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema({probatio.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EaseeOcppOptionsFlow:
        """Options of the integration."""
        return EaseeOcppOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Chargers are added one by one with the setup wizard."""
        return {SUBENTRY_TYPE_CHARGER: OcppChargerSubentryFlow}


class EaseeOcppOptionsFlow(OptionsFlow):
    """RFID behaviour."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Accept every card instead of only the cards registered as tags."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_ACCEPT_ALL_CARDS, False)
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema({probatio.Optional(CONF_ACCEPT_ALL_CARDS, default=current): BooleanSelector()}),
        )
