"""Binary sensor platform for SkylinkNet."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkylinkNetRuntimeData
from .const import (
    ATTR_BATTERY_OK,
    ATTR_DEVICE_ID,
    ATTR_EVENT_TIME,
    ATTR_RAW_STATUS,
    CONF_DEFAULT_DEVICE_CLASS,
    DEFAULT_DEVICE_CLASS,
    DEVICE_CLASS_NONE,
    DOMAIN,
)
from .hub import SkylinkNetDeviceState, SkylinkNetHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SkylinkNet binary sensors."""
    data: SkylinkNetRuntimeData = hass.data[DOMAIN][entry.entry_id]
    hub = data.hub
    known_devices: set[str] = set()

    @callback
    def async_add_device(device_id: str) -> None:
        if device_id in known_devices or device_id in data.ignored_device_ids:
            return
        known_devices.add(device_id)
        async_add_entities([SkylinkNetBinarySensor(hub, entry, device_id)])

    @callback
    def async_handle_device(device: SkylinkNetDeviceState) -> None:
        if device.device_id in data.ignored_device_ids:
            hub.devices.pop(device.device_id, None)
            return
        if device.device_id not in data.known_device_ids:
            data.known_device_ids.add(device.device_id)
            hass.async_create_task(data.async_save_known_devices())
        async_add_device(device.device_id)

    entry.async_on_unload(hub.async_subscribe_device(async_handle_device))
    for device_id in data.known_device_ids:
        async_add_device(device_id)
    for device in list(hub.devices.values()):
        async_handle_device(device)


class SkylinkNetBinarySensor(BinarySensorEntity):
    """SkylinkNet cloud event binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, hub: SkylinkNetHub, entry: ConfigEntry, device_id: str) -> None:
        self._hub = hub
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{hub.hub_id}_{device_id}"
        self._attr_translation_key = "device"
        self._attr_translation_placeholders = {"device_id": _short_device_id(device_id)}
        self._attr_device_class = _device_class(entry)

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._hub.connected and self._state is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is active."""
        state = self._state
        return None if state is None else state.is_on

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return diagnostic state attributes."""
        state = self._state
        attrs: dict[str, object] = {ATTR_DEVICE_ID: self._device_id}
        if state is None:
            return attrs
        attrs[ATTR_RAW_STATUS] = state.status
        if state.battery_ok is not None:
            attrs[ATTR_BATTERY_OK] = state.battery_ok
        if state.event_time:
            attrs[ATTR_EVENT_TIME] = state.event_time
        return attrs

    @property
    def device_info(self) -> dict[str, object]:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._hub.hub_id, self._device_id)},
            "name": f"SkylinkNet {_short_device_id(self._device_id)}",
            "manufacturer": "Skylink",
            "model": "SkylinkNet sensor",
        }

    @property
    def _state(self) -> SkylinkNetDeviceState | None:
        return self._hub.devices.get(self._device_id)

    async def async_added_to_hass(self) -> None:
        """Subscribe to hub updates."""

        @callback
        def handle_device(device: SkylinkNetDeviceState) -> None:
            if device.device_id == self._device_id:
                self.async_write_ha_state()

        @callback
        def handle_availability(_: bool) -> None:
            self.async_write_ha_state()

        self.async_on_remove(self._hub.async_subscribe_device(handle_device))
        self.async_on_remove(self._hub.async_subscribe_availability(handle_availability))


def _device_class(entry: ConfigEntry) -> BinarySensorDeviceClass | None:
    value = entry.options.get(CONF_DEFAULT_DEVICE_CLASS, DEFAULT_DEVICE_CLASS)
    if value == DEVICE_CLASS_NONE:
        return None
    return BinarySensorDeviceClass(value)


def _short_device_id(device_id: str) -> str:
    return device_id[-6:] if len(device_id) > 6 else device_id
