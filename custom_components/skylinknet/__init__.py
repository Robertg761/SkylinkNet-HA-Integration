"""SkylinkNet integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CONFIG_ENTRY_ID,
    CONF_HUB_ID,
    CONF_HUB_KEY,
    CONF_IGNORE_FUTURE_EVENTS,
    CONF_SKYLINKNET_DEVICE_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_ALLOW_DEVICE,
    SERVICE_FORGET_DEVICE,
)
from .hub import SkylinkNetHub

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

FORGET_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SKYLINKNET_DEVICE_ID): cv.string,
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(CONF_IGNORE_FUTURE_EVENTS, default=True): cv.boolean,
    }
)

ALLOW_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SKYLINKNET_DEVICE_ID): cv.string,
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
    }
)


@dataclass(slots=True)
class SkylinkNetRuntimeData:
    """Runtime data for one SkylinkNet config entry."""

    hub: SkylinkNetHub
    store: Store
    known_device_ids: set[str]
    ignored_device_ids: set[str]

    async def async_save_known_devices(self) -> None:
        """Persist known device IDs."""
        await self.store.async_save(
            {
                "device_ids": sorted(self.known_device_ids),
                "ignored_device_ids": sorted(self.ignored_device_ids),
            }
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up SkylinkNet services."""
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SkylinkNet from a config entry."""
    _async_register_services(hass)
    session = async_get_clientsession(hass)
    hub = SkylinkNetHub(
        hub_id=entry.data[CONF_HUB_ID],
        hub_key=entry.data[CONF_HUB_KEY],
        session=session,
    )
    store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    stored = await store.async_load() or {}
    known_device_ids = set(stored.get("device_ids", []))
    ignored_device_ids = set(stored.get("ignored_device_ids", []))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SkylinkNetRuntimeData(
        hub=hub,
        store=store,
        known_device_ids=known_device_ids,
        ignored_device_ids=ignored_device_ids,
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow users to remove a SkylinkNet device from the UI."""
    data: SkylinkNetRuntimeData | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data is None:
        return False

    device_id = _device_id_from_device_entry(device_entry, data.hub.hub_id)
    if device_id is None:
        return False

    data.known_device_ids.discard(device_id)
    data.hub.devices.pop(device_id, None)
    data.ignored_device_ids.add(device_id)
    await data.async_save_known_devices()
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register SkylinkNet management services."""
    if not hass.services.has_service(DOMAIN, SERVICE_FORGET_DEVICE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FORGET_DEVICE,
            _async_forget_device_service,
            schema=FORGET_DEVICE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_ALLOW_DEVICE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ALLOW_DEVICE,
            _async_allow_device_service,
            schema=ALLOW_DEVICE_SCHEMA,
        )


async def _async_forget_device_service(call: ServiceCall) -> None:
    """Forget a SkylinkNet device and optionally ignore future events for it."""
    device_id: str = call.data[CONF_SKYLINKNET_DEVICE_ID]
    config_entry_id: str | None = call.data.get(CONF_CONFIG_ENTRY_ID)
    ignore_future_events: bool = call.data[CONF_IGNORE_FUTURE_EVENTS]
    hass = call.hass
    matched = False

    for entry_id, data in _matching_runtime_data(hass, config_entry_id):
        should_update_entry = (
            device_id in data.known_device_ids
            or device_id in data.hub.devices
            or _async_registry_has_device(hass, data.hub.hub_id, device_id)
        )
        if not should_update_entry:
            continue

        matched = True
        data.known_device_ids.discard(device_id)
        data.hub.devices.pop(device_id, None)
        if ignore_future_events:
            data.ignored_device_ids.add(device_id)
        await data.async_save_known_devices()
        _async_remove_from_registries(hass, data.hub.hub_id, device_id)
        await hass.config_entries.async_reload(entry_id)

    if not matched:
        raise HomeAssistantError(f"SkylinkNet device {device_id} was not found")


async def _async_allow_device_service(call: ServiceCall) -> None:
    """Allow a previously ignored SkylinkNet device to be discovered again."""
    device_id: str = call.data[CONF_SKYLINKNET_DEVICE_ID]
    config_entry_id: str | None = call.data.get(CONF_CONFIG_ENTRY_ID)
    matched = False

    for _entry_id, data in _matching_runtime_data(call.hass, config_entry_id):
        if device_id not in data.ignored_device_ids:
            continue
        matched = True
        data.ignored_device_ids.remove(device_id)
        await data.async_save_known_devices()

    if not matched:
        raise HomeAssistantError(f"SkylinkNet device {device_id} was not ignored")


def _device_id_from_device_entry(device_entry: dr.DeviceEntry, hub_id: str) -> str | None:
    """Return the SkylinkNet device ID from a Home Assistant device entry."""
    for identifier in device_entry.identifiers:
        if len(identifier) == 2 and identifier[0] == DOMAIN:
            unique_id = identifier[1]
            prefix = f"{hub_id}_"
            if unique_id.startswith(prefix):
                return unique_id.removeprefix(prefix)
        if len(identifier) == 3 and identifier[:2] == (DOMAIN, hub_id):
            return identifier[2]
    return None


def _matching_runtime_data(
    hass: HomeAssistant, config_entry_id: str | None
) -> list[tuple[str, SkylinkNetRuntimeData]]:
    """Return runtime data matching an optional config entry ID."""
    all_data: dict[str, SkylinkNetRuntimeData] = hass.data.get(DOMAIN, {})
    if config_entry_id is None:
        return list(all_data.items())
    if config_entry_id not in all_data:
        raise HomeAssistantError(f"SkylinkNet config entry {config_entry_id} was not found")
    return [(config_entry_id, all_data[config_entry_id])]


def _async_registry_has_device(hass: HomeAssistant, hub_id: str, device_id: str) -> bool:
    """Return whether Home Assistant registries contain this SkylinkNet device."""
    entity_registry = er.async_get(hass)
    if entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, _unique_id(hub_id, device_id)
    ):
        return True

    device_registry = dr.async_get(hass)
    return _async_get_device_entry(device_registry, hub_id, device_id) is not None


def _async_remove_from_registries(hass: HomeAssistant, hub_id: str, device_id: str) -> None:
    """Remove a SkylinkNet device's entity and device registry entries."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, _unique_id(hub_id, device_id)
    )
    if entity_id:
        entity_registry.async_remove(entity_id)

    device_registry = dr.async_get(hass)
    device_entry = _async_get_device_entry(device_registry, hub_id, device_id)
    if device_entry:
        device_registry.async_remove_device(device_entry.id)


def _async_get_device_entry(
    device_registry: dr.DeviceRegistry, hub_id: str, device_id: str
) -> dr.DeviceEntry | None:
    """Return a device entry by current or legacy SkylinkNet identifiers."""
    for identifiers in _device_identifier_sets(hub_id, device_id):
        if device_entry := device_registry.async_get_device(identifiers=identifiers):
            return device_entry
    return None


def _device_identifier_sets(hub_id: str, device_id: str) -> tuple[set[tuple[Any, ...]], ...]:
    """Return current and legacy SkylinkNet device registry identifiers."""
    return (
        {(DOMAIN, _unique_id(hub_id, device_id))},
        {(DOMAIN, hub_id, device_id)},
    )


def _unique_id(hub_id: str, device_id: str) -> str:
    """Return the binary sensor unique ID for a SkylinkNet device."""
    return f"{hub_id}_{device_id}"
