"""SkylinkNet cloud WebSocket client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from typing import Any
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

WS_BASE_URL = "wss://api-1.skyhm.net/websock/hu"
ALARM_DEVICE_ID = "F0000000"


class SkylinkNetError(Exception):
    """Base SkylinkNet error."""


class SkylinkNetAuthError(SkylinkNetError):
    """Raised when the hub ID/key is rejected."""


class SkylinkNetConnectionError(SkylinkNetError):
    """Raised when the WebSocket connection fails."""


@dataclass(slots=True)
class SkylinkNetDeviceState:
    """Last known state for a SkylinkNet device."""

    device_id: str
    status: int
    battery: int | None = None
    event_time: str | None = None
    last_seen: datetime | None = None

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor should be on."""
        return self.status != 0

    @property
    def battery_ok(self) -> bool | None:
        """Return battery health when the protocol provides it."""
        if self.battery is None:
            return None
        return self.battery == 1


@dataclass(slots=True)
class SkylinkNetEvent:
    """Parsed SkylinkNet event."""

    op: str
    hub_id: str | None
    devices: list[SkylinkNetDeviceState]


@dataclass(slots=True)
class SkylinkNetHello:
    """Initial cloud WebSocket hello."""

    keepalive_interval: int | None = None
    super_user: int | None = None


@dataclass(slots=True)
class SkylinkNetPing:
    """Text keepalive sent by the cloud WebSocket."""


ParsedMessage = SkylinkNetEvent | SkylinkNetHello | SkylinkNetPing | None
DeviceCallback = Callable[[SkylinkNetDeviceState], None]
AvailabilityCallback = Callable[[bool], None]


def build_websocket_url(hub_id: str, hub_key: str) -> str:
    """Build the SkylinkNet cloud WebSocket URL."""
    return f"{WS_BASE_URL}/{quote(hub_id, safe='')}/{quote(hub_key, safe='')}"


def parse_skylinknet_message(text: str) -> ParsedMessage:
    """Parse one text message from the SkylinkNet cloud WebSocket."""
    if text == "PING":
        return SkylinkNetPing()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        _LOGGER.debug("Ignoring non-JSON SkylinkNet message: %s", text)
        return None

    if not isinstance(payload, dict):
        return None

    data = payload.get("data")
    if payload.get("errno") == 0 and isinstance(data, dict):
        return SkylinkNetHello(
            keepalive_interval=_as_int(data.get("keepalive_interval")),
            super_user=_as_int(data.get("super_user")),
        )

    op = payload.get("op")
    if op not in {"report", "read"} or not isinstance(data, list):
        return None

    devices: list[SkylinkNetDeviceState] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        device_id = item.get("dev_id")
        status = _as_int(item.get("status"))
        if not device_id or status is None:
            continue
        devices.append(
            SkylinkNetDeviceState(
                device_id=str(device_id),
                status=status,
                battery=_as_int(item.get("battery")),
                event_time=_as_str(item.get("time")),
                last_seen=datetime.now(UTC),
            )
        )

    return SkylinkNetEvent(op=str(op), hub_id=_as_str(payload.get("hub_id")), devices=devices)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class SkylinkNetHub:
    """Maintain a SkylinkNet cloud WebSocket connection."""

    def __init__(self, hub_id: str, hub_key: str, session: Any) -> None:
        self.hub_id = hub_id
        self._hub_key = hub_key
        self._session = session
        self.devices: dict[str, SkylinkNetDeviceState] = {}
        self.keepalive_interval: int | None = None
        self.super_user: int | None = None
        self.connected = False
        self._closed = False
        self._task: asyncio.Task[None] | None = None
        self._device_callbacks: set[DeviceCallback] = set()
        self._availability_callbacks: set[AvailabilityCallback] = set()

    @property
    def websocket_url(self) -> str:
        """Return the cloud WebSocket URL."""
        return build_websocket_url(self.hub_id, self._hub_key)

    async def async_validate(self, timeout: float = 10.0) -> None:
        """Validate hub credentials by opening the cloud WebSocket."""
        try:
            async with asyncio.timeout(timeout):
                async with self._session.ws_connect(self.websocket_url, heartbeat=60) as ws:
                    msg = await ws.receive()
                    data = getattr(msg, "data", None)
                    if not isinstance(data, str):
                        raise SkylinkNetAuthError("Did not receive a text hello from SkylinkNet")
                    parsed = parse_skylinknet_message(data)
                    if not isinstance(parsed, SkylinkNetHello):
                        raise SkylinkNetAuthError("SkylinkNet did not accept this hub ID/key")
        except SkylinkNetAuthError:
            raise
        except TimeoutError as exc:
            raise SkylinkNetConnectionError("Timed out connecting to SkylinkNet") from exc
        except Exception as exc:
            raise SkylinkNetConnectionError(f"Could not connect to SkylinkNet: {exc}") from exc

    async def async_start(self) -> None:
        """Start the background listener."""
        if self._task and not self._task.done():
            return
        self._closed = False
        self._task = asyncio.create_task(self._run_forever(), name="skylinknet-websocket")

    async def async_stop(self) -> None:
        """Stop the background listener."""
        self._closed = True
        task = self._task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._set_connected(False)

    def async_subscribe_device(self, callback: DeviceCallback) -> Callable[[], None]:
        """Subscribe to device state changes."""
        self._device_callbacks.add(callback)

        def remove() -> None:
            self._device_callbacks.discard(callback)

        return remove

    def async_subscribe_availability(self, callback: AvailabilityCallback) -> Callable[[], None]:
        """Subscribe to connection availability changes."""
        self._availability_callbacks.add(callback)

        def remove() -> None:
            self._availability_callbacks.discard(callback)

        return remove

    async def _run_forever(self) -> None:
        delay = 1
        while not self._closed:
            try:
                await self._connect_once()
                delay = 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._set_connected(False)
                _LOGGER.warning("SkylinkNet WebSocket disconnected: %s", exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connect_once(self) -> None:
        from aiohttp import WSMsgType

        async with self._session.ws_connect(self.websocket_url, heartbeat=60) as ws:
            self._set_connected(True)
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    self._handle_text(msg.data)
                elif msg.type == WSMsgType.ERROR:
                    raise SkylinkNetConnectionError(f"WebSocket error: {ws.exception()}")
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED):
                    break
        raise SkylinkNetConnectionError("WebSocket closed")

    def _handle_text(self, text: str) -> None:
        parsed = parse_skylinknet_message(text)
        if isinstance(parsed, SkylinkNetPing) or parsed is None:
            return
        if isinstance(parsed, SkylinkNetHello):
            self.keepalive_interval = parsed.keepalive_interval
            self.super_user = parsed.super_user
            return
        for device in parsed.devices:
            if device.device_id == ALARM_DEVICE_ID:
                _LOGGER.debug("Ignoring alarm pseudo-device event")
                continue
            self.devices[device.device_id] = device
            for callback in tuple(self._device_callbacks):
                callback(device)

    def _set_connected(self, connected: bool) -> None:
        if self.connected == connected:
            return
        self.connected = connected
        for callback in tuple(self._availability_callbacks):
            callback(connected)
