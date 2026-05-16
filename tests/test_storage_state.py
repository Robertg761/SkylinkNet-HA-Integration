"""Tests for SkylinkNet stored state helpers."""

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE_PATH = ROOT / "custom_components" / "skylinknet"

package = types.ModuleType("skylinknet")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules["skylinknet"] = package


def _stub_module(name: str, **attrs: object) -> None:
    module = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(module, attr_name, value)
    sys.modules[name] = module


class _ConfigEntry:
    pass


class _HomeAssistant:
    pass


class _ServiceCall:
    pass


class _HomeAssistantError(Exception):
    pass


_stub_module("homeassistant", config_entries=types.ModuleType("homeassistant.config_entries"))
_stub_module("homeassistant.config_entries", ConfigEntry=_ConfigEntry)
_stub_module(
    "homeassistant.core",
    HomeAssistant=_HomeAssistant,
    ServiceCall=_ServiceCall,
)
_stub_module("homeassistant.exceptions", HomeAssistantError=_HomeAssistantError)
_stub_module("homeassistant.helpers", aiohttp_client=types.ModuleType("aiohttp_client"))
_stub_module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: None)
_stub_module("homeassistant.helpers.config_validation", string=str, boolean=bool)
_stub_module("homeassistant.helpers.device_registry", DeviceEntry=object, DeviceRegistry=object)
_stub_module("homeassistant.helpers.entity_registry")
_stub_module("homeassistant.helpers.storage", Store=object)
_stub_module("voluptuous", Schema=lambda schema: schema, Required=lambda key: key, Optional=lambda key, default=None: key)

spec = importlib.util.spec_from_file_location("skylinknet", PACKAGE_PATH / "__init__.py")
skylinknet = importlib.util.module_from_spec(spec)
sys.modules["skylinknet"] = skylinknet
assert spec.loader is not None
spec.loader.exec_module(skylinknet)

SkylinkNetDeviceState = skylinknet.SkylinkNetDeviceState


class TestStorageState(unittest.TestCase):
    """Test stored state serialization."""

    def test_serializes_last_known_device_states(self) -> None:
        last_seen = datetime(2026, 5, 16, 23, 19, 18, tzinfo=UTC)

        self.assertEqual(
            skylinknet._serialize_device_states(
                {
                    "000004CE": SkylinkNetDeviceState(
                        device_id="000004CE",
                        status=0,
                        battery=1,
                        event_time="202605162319",
                        last_seen=last_seen,
                    )
                }
            ),
            {
                "000004CE": {
                    "status": 0,
                    "battery": 1,
                    "event_time": "202605162319",
                    "last_seen": "2026-05-16T23:19:18+00:00",
                }
            },
        )

    def test_deserializes_valid_states_and_ignores_invalid_states(self) -> None:
        states = skylinknet._deserialize_device_states(
            {
                "000004CE": {
                    "status": "0",
                    "battery": "1",
                    "event_time": "202605162319",
                    "last_seen": "2026-05-16T23:19:18+00:00",
                },
                "bad": {"status": "not-an-int"},
            }
        )

        self.assertEqual(set(states), {"000004CE"})
        self.assertEqual(states["000004CE"].status, 0)
        self.assertEqual(states["000004CE"].battery, 1)
        self.assertEqual(states["000004CE"].event_time, "202605162319")
        self.assertEqual(states["000004CE"].last_seen, datetime(2026, 5, 16, 23, 19, 18, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
