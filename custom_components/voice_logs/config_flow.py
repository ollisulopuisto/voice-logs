"""Config flow for Voice Logs."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class VoiceLogsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the single Voice Logs instance."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create the zero-configuration entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Voice Logs", data={})
