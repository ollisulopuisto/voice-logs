"""Latest Assist exchange sensor."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_STORES, DOMAIN, UPDATED_EVENT
from .store import TranscriptStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the latest conversation sensor."""
    store: TranscriptStore = hass.data[DOMAIN][DATA_STORES][entry.entry_id]
    async_add_entities([LatestConversationSensor(hass, entry, store)])


class LatestConversationSensor(Entity):
    """Expose the last full answer as attributes and a short sensor state."""

    _attr_has_entity_name = False
    _attr_name = "Voice Logs Latest"
    _attr_icon = "mdi:message-text-clock-outline"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: TranscriptStore
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.store = store
        self._attr_unique_id = f"{entry.entry_id}-latest"
        self._remove_listener = None

    @property
    def native_value(self) -> str | None:
        latest = self.store.latest
        if not latest:
            return None
        text = latest.get("answer") or latest.get("query") or ""
        return str(text)[:255]

    @property
    def extra_state_attributes(self) -> dict:
        latest = self.store.latest
        return {
            "question": latest.get("query") if latest else None,
            "answer": latest.get("answer") if latest else None,
            "created_at": latest.get("created_at") if latest else None,
            "run_id": latest.get("run_id") if latest else None,
            "debug": latest.get("debug") if latest else None,
            "active": self.store.active_turn,
            "total_conversations": len(self.store.records),
            "history_updated": self.store.updated_at,
        }

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self.hass.bus.async_listen(
            UPDATED_EVENT, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()

    @callback
    def _handle_update(self, event) -> None:
        if event.data.get("entry_id") == self.entry.entry_id:
            self.async_write_ha_state()
