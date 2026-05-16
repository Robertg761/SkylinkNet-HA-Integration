"""SkylinkNet integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import CONF_HUB_ID, CONF_HUB_KEY, DOMAIN, PLATFORMS
from .hub import SkylinkNetHub

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


@dataclass(slots=True)
class SkylinkNetRuntimeData:
    """Runtime data for one SkylinkNet config entry."""

    hub: SkylinkNetHub
    store: Store
    known_device_ids: set[str]

    async def async_save_known_devices(self) -> None:
        """Persist known device IDs."""
        await self.store.async_save({"device_ids": sorted(self.known_device_ids)})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SkylinkNet from a config entry."""
    session = async_get_clientsession(hass)
    hub = SkylinkNetHub(
        hub_id=entry.data[CONF_HUB_ID],
        hub_key=entry.data[CONF_HUB_KEY],
        session=session,
    )
    store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    stored = await store.async_load() or {}
    known_device_ids = set(stored.get("device_ids", []))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SkylinkNetRuntimeData(
        hub=hub,
        store=store,
        known_device_ids=known_device_ids,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hub.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SkylinkNet config entry."""
    data: SkylinkNetRuntimeData = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await data.hub.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options update."""
    await hass.config_entries.async_reload(entry.entry_id)
