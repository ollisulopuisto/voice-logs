"""Read-only Assist pipeline monitor and transcript archiver."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    TrackStates,
    async_track_state_change_filtered,
    async_track_time_interval,
)

from .history import ServiceActionCapture, active_pipeline_runs, parse_all
from .store import TranscriptStore

_LOGGER = logging.getLogger(__name__)
POLL_INTERVAL = timedelta(seconds=1)


class AssistHistoryCoordinator:
    """Poll Home Assistant's debug store without modifying its pipeline code."""

    def __init__(self, hass: HomeAssistant, store: TranscriptStore) -> None:
        self.hass = hass
        self.store = store
        self._refresh_lock = asyncio.Lock()
        self._started = False
        self._service_capture = ServiceActionCapture()

    async def async_start(self, entry) -> None:
        """Start the safety poll and satellite-state refresh listener."""
        if self._started:
            return
        self._started = True
        entry.async_on_unload(self.hass.bus.async_listen("call_service", self._on_service_call))
        entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_interval_refresh, POLL_INTERVAL
            )
        )
        entry.async_on_unload(
            async_track_state_change_filtered(
                self.hass,
                TrackStates(False, set(), {"assist_satellite"}),
                self._on_satellite_state,
            )
        )
        await self.async_refresh()

    @callback
    def _on_service_call(self, event: Event) -> None:
        self._service_capture.record(event, active_pipeline_runs(self.hass))

    @callback
    def _on_satellite_state(self, _event: Event) -> None:
        self.hass.async_create_task(self.async_refresh())

    @callback
    def _async_interval_refresh(self, _now) -> None:
        self.hass.async_create_task(self.async_refresh())

    async def async_refresh(self) -> None:
        """Publish an active turn and archive any completed runs we have not seen."""
        async with self._refresh_lock:
            try:
                turns = parse_all(self.hass)
                self._service_capture.enrich(turns, active_pipeline_runs(self.hass))
            except Exception as err:  # Guard the live Assist path from internal API drift.
                _LOGGER.warning("Could not read Assist debug history: %s", err)
                return

            active = next(
                (turn for turn in turns if not turn["finished"]),
                None,
            )
            await self.store.async_set_active(active)

            # The debug store is newest first; insert old-to-new so the archive
            # remains newest first as each record is prepended.
            for turn in reversed(turns):
                if turn["finished"]:
                    await self.store.async_add(turn)
