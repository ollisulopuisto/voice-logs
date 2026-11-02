"""Voice Logs custom integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
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
from .acl import can_read
from .coordinator import AssistHistoryCoordinator
from .store import TranscriptStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
    """Serve the card file and load it in the frontend.

    The card becomes available on every dashboard without editing any dashboard or the user's
    resource list. The user still decides where to place the card.
    """
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}", str(CARD_DIRECTORY), cache_headers=True)]
    )
    add_extra_js_url(hass, CARD_RESOURCE_URL)



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


def _allowed_user_ids(hass: HomeAssistant) -> list[str]:
    """User IDs chosen in the integration options (admins are always allowed)."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return list(entries[0].options.get("allowed_user_ids", [])) if entries else []


def _can_read(hass: HomeAssistant, user) -> bool:
    """Whether this user may read the conversation archive."""
    return can_read(bool(user and user.is_admin), getattr(user, "id", None), _allowed_user_ids(hass))


async def _require_reader(hass: HomeAssistant, call: ServiceCall) -> None:
    """Service calls from a user must come from someone allowed to read the archive.

    Automations and scripts have no user in their context and are trusted.
    """
    user_id = call.context.user_id
    if user_id is None:
        return
    user = await hass.auth.async_get_user(user_id)
    if not _can_read(hass, user):
        raise HomeAssistantError("Ei oikeutta keskusteluarkistoon")


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
    """Return a filtered page from the persistent archive, plus the live and latest exchange."""
    if not _can_read(hass, connection.user):
        connection.send_error(msg["id"], "unauthorized", "Ei oikeutta keskusteluarkistoon")
        return
    store = _get_store(hass)
    page = store.page(
        query=msg["query"],
        include_hidden=msg["include_hidden"],
        offset=msg["offset"],
        limit=msg["limit"],
    )
    connection.send_result(
        msg["id"],
        {**page, "active": store.active_turn, "latest": store.latest},
    )


async def _async_hide_conversation(call) -> None:
    """Hide one transcript without deleting it."""
    await _require_reader(call.hass, call)
    store = _get_store(call.hass)
    if not await store.async_set_hidden(call.data["conversation_id"], True):
        raise HomeAssistantError("Conversation was not found or was already hidden")


async def _async_restore_conversation(call) -> None:
    """Restore a hidden transcript to the normal history view."""
    await _require_reader(call.hass, call)
    store = _get_store(call.hass)
    if not await store.async_set_hidden(call.data["conversation_id"], False):
        raise HomeAssistantError("Conversation was not found or was already visible")
