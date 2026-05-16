"""Diagnostics for SkylinkNet."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from . import SkylinkNetRuntimeData
from .const import CONF_HUB_ID, CONF_HUB_KEY, DOMAIN

TO_REDACT = {CONF_HUB_ID, CONF_HUB_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: SkylinkNetRuntimeData | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    hub = data.hub if data else None

    return {
        "entry": {
            "data": _redact_dict(entry.data),
            "options": dict(entry.options),
        },
        "runtime": {
            "connected": hub.connected if hub else None,
            "known_device_count": len(hub.devices) if hub else 0,
            "stored_device_count": len(data.known_device_ids) if data else 0,
            "stored_device_state_count": len(data.known_device_states) if data else 0,
            "ignored_device_count": len(data.ignored_device_ids) if data else 0,
            "keepalive_interval": hub.keepalive_interval if hub else None,
            "super_user": hub.super_user if hub else None,
        },
        "device_registry_count": len(
            dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        ),
        "entity_registry_count": len(
            er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        ),
    }


def _redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(data)
    for key in TO_REDACT:
        if key in redacted:
            redacted[key] = "**REDACTED**"
    return redacted
