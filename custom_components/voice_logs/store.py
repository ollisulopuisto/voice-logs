"""Persistent transcript archive and hidden-state management."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, UPDATED_EVENT
from .history import history_page

STORE_VERSION = 1


class TranscriptStore:
    """Keep all completed text turns; the UI pages over this archive."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}_{entry_id}_transcripts")
        self._write_lock = asyncio.Lock()
        self.records: list[dict[str, Any]] = []
        self.active_turn: dict[str, Any] | None = None
        self.updated_at = ""

    async def async_load(self) -> None:
        """Restore the durable transcript archive."""
        data = await self._store.async_load()
        records = data.get("records", []) if isinstance(data, dict) else []
        self.records = records if isinstance(records, list) else []
        self.updated_at = str(data.get("updated_at", "")) if isinstance(data, dict) else ""

    @property
    def latest(self) -> dict[str, Any] | None:
        return self.records[0] if self.records else None

    async def async_add(self, turn: dict[str, Any]) -> bool:
        """Persist a completed pipeline run once, keyed by its stable run ID."""
        run_id = str(turn.get("run_id") or turn.get("id") or "")
        if not run_id or not turn.get("finished"):
            return False
        async with self._write_lock:
            if any(record.get("run_id") == run_id for record in self.records):
                return False
            record = {**turn, "id": run_id, "run_id": run_id, "hidden": False}
            self.records.insert(0, record)
            await self._async_save()
        return True

    async def async_set_hidden(self, conversation_id: str, hidden: bool) -> bool:
        """Hide or restore a turn without deleting its data."""
        async with self._write_lock:
            record = next(
                (item for item in self.records if item.get("id") == conversation_id),
                None,
            )
            if record is None or bool(record.get("hidden")) == hidden:
                return False
            record["hidden"] = hidden
            await self._async_save()
        return True

    async def async_set_active(self, turn: dict[str, Any] | None) -> bool:
        """Publish the in-progress exchange without adding it to durable history."""
        if turn == self.active_turn:
            return False
        self.active_turn = turn
        self._fire_updated()
        return True

    def page(
        self,
        *,
        query: str = "",
        include_hidden: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return a bounded page from the full archive."""
        return history_page(
            self.records,
            query=query,
            include_hidden=include_hidden,
            offset=offset,
            limit=limit,
        )

    async def _async_save(self) -> None:
        self.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        await self._store.async_save(
            {"records": self.records, "updated_at": self.updated_at}
        )
        self._fire_updated()

    def _fire_updated(self) -> None:
        self.hass.bus.async_fire(UPDATED_EVENT, {"entry_id": self.entry_id})
