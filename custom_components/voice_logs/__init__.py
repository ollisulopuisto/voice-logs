"""Voice Logs custom integration."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

import probatio
import voluptuous as vol

from .const import (
    CARD_URL,
    CARD_VERSION,
    DATA_COORDINATORS,
    DATA_STORES,
    DOMAIN,
)
from .coordinator import AssistHistoryCoordinator
from .store import TranscriptStore

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
CARD_DIRECTORY = Path(__file__).parent / "www"
CARD_RESOURCE_URL = f"{CARD_URL}?v={CARD_VERSION}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the card resource, history API, and hide/restore actions."""
    hass.data.setdefault(DOMAIN, {DATA_STORES: {}, DATA_COORDINATORS: {}})
    await _async_register_card(hass)
    websocket_api.async_register_command(hass, websocket_get_history)
    hass.services.async_register(
        DOMAIN,
        "hide_conversation",
        _async_hide_conversation,
        schema=vol.Schema({vol.Required("conversation_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "restore_conversation",
        _async_restore_conversation,
        schema=vol.Schema({vol.Required("conversation_id"): cv.string}),
    )
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled card and register it in storage-mode dashboards."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}", str(CARD_DIRECTORY), cache_headers=True)]
    )

    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.warning(
            "Lovelace is not ready; add card resource %s manually if needed",
            CARD_RESOURCE_URL,
        )
        return

    try:
        await resources.async_get_info()  # Load storage before inspecting items.
        if not hasattr(resources, "async_create_item"):
            _LOGGER.info(
                "Voice Logs card is served at %s; add it to YAML-mode Lovelace resources",
                CARD_RESOURCE_URL,
            )
            return

        resource = next(
            (
                item
                for item in resources.async_items()
                if urlsplit(item.get("url", "")).path == CARD_URL
            ),
            None,
        )
        if resource is None:
            await resources.async_create_item(
                {"res_type": "module", "url": CARD_RESOURCE_URL}
            )
        elif resource.get("url") != CARD_RESOURCE_URL:
            await resources.async_update_item(
                resource["id"], {"res_type": "module", "url": CARD_RESOURCE_URL}
            )
    except Exception as err:  # Dashboard resource failure must not disable logging.
        _LOGGER.warning(
            "Could not auto-register the Voice Logs card: %s. Add %s in Settings > Dashboards > Resources.",
            err,
            CARD_RESOURCE_URL,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the archive and begin monitoring Assist runs."""
    domain_data = hass.data.setdefault(DOMAIN, {DATA_STORES: {}, DATA_COORDINATORS: {}})
    store = TranscriptStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = AssistHistoryCoordinator(hass, store)
    domain_data[DATA_STORES][entry.entry_id] = store
    domain_data[DATA_COORDINATORS][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start(entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities and in-memory services state."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.get(DATA_STORES, {}).pop(entry.entry_id, None)
    domain_data.get(DATA_COORDINATORS, {}).pop(entry.entry_id, None)
    return True


def _get_store(hass: HomeAssistant) -> TranscriptStore:
    """Return the single configured transcript store."""
    stores = hass.data.get(DOMAIN, {}).get(DATA_STORES, {})
    if not stores:
        raise HomeAssistantError("Add the Voice Logs integration before using its history")
    return next(iter(stores.values()))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/history/list",
        probatio.Optional("query", default=""): str,
        probatio.Optional("include_hidden", default=False): bool,
        probatio.Optional("offset", default=0): int,
        probatio.Optional("limit", default=20): int,
    }
)
@callback
def websocket_get_history(hass, connection, msg) -> None:
    """Return a filtered page from the persistent archive."""
    store = _get_store(hass)
    connection.send_result(
        msg["id"],
        store.page(
            query=msg["query"],
            include_hidden=msg["include_hidden"],
            offset=msg["offset"],
            limit=msg["limit"],
        ),
    )


async def _async_hide_conversation(call) -> None:
    """Hide one transcript without deleting it."""
    store = _get_store(call.hass)
    if not await store.async_set_hidden(call.data["conversation_id"], True):
        raise HomeAssistantError("Conversation was not found or was already hidden")


async def _async_restore_conversation(call) -> None:
    """Restore a hidden transcript to the normal history view."""
    store = _get_store(call.hass)
    if not await store.async_set_hidden(call.data["conversation_id"], False):
        raise HomeAssistantError("Conversation was not found or was already visible")
