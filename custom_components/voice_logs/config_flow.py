"""Config and options flow for Voice Logs."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN


class VoiceLogsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the single Voice Logs instance."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create the zero-configuration entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Voice Logs", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Options: which users, besides administrators, may read the archive."""
        return VoiceLogsOptionsFlow()


class VoiceLogsOptionsFlow(config_entries.OptionsFlow):
    """Choose the users allowed to read the conversation archive."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        users = [u for u in await self.hass.auth.async_get_users() if not u.system_generated]
        options = [selector.SelectOptionDict(value=u.id, label=u.name) for u in users]
        current = self.config_entry.options.get("allowed_user_ids", [])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "retention_days",
                        default=int(self.config_entry.options.get("retention_days", 90)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=3650,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="days",
                        )
                    ),
                    vol.Optional("allowed_user_ids", default=current): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
