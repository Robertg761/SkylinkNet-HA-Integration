"""Tests for SkylinkNet message parsing."""

import importlib.util
from pathlib import Path
import sys
import unittest

HUB_PATH = Path(__file__).parents[1] / "custom_components" / "skylinknet" / "hub.py"
spec = importlib.util.spec_from_file_location("skylinknet_hub", HUB_PATH)
hub = importlib.util.module_from_spec(spec)
sys.modules["skylinknet_hub"] = hub
assert spec.loader is not None
spec.loader.exec_module(hub)

SkylinkNetEvent = hub.SkylinkNetEvent
SkylinkNetHello = hub.SkylinkNetHello
SkylinkNetPing = hub.SkylinkNetPing
SkylinkNetHub = hub.SkylinkNetHub
build_websocket_url = hub.build_websocket_url
parse_skylinknet_message = hub.parse_skylinknet_message


class TestSkylinkNetParser(unittest.TestCase):
    """Test the pure protocol parser."""

    def test_parse_hello(self) -> None:
        msg = parse_skylinknet_message('{"data":{"keepalive_interval":30,"super_user":1},"errno":0}')

        self.assertIsInstance(msg, SkylinkNetHello)
        assert isinstance(msg, SkylinkNetHello)
        self.assertEqual(msg.keepalive_interval, 30)
        self.assertEqual(msg.super_user, 1)

    def test_parse_ping(self) -> None:
        self.assertIsInstance(parse_skylinknet_message("PING"), SkylinkNetPing)

    def test_parse_report(self) -> None:
        msg = parse_skylinknet_message(
            '{"hub_id":"123456","data":[{"battery":1,"time":"202605152010","status":1,'
            '"dev_id":"ABCDEF12"}],"op":"report"}'
        )

        self.assertIsInstance(msg, SkylinkNetEvent)
        assert isinstance(msg, SkylinkNetEvent)
        self.assertEqual(msg.op, "report")
        self.assertEqual(msg.hub_id, "123456")
        self.assertEqual(len(msg.devices), 1)
        device = msg.devices[0]
        self.assertEqual(device.device_id, "ABCDEF12")
        self.assertEqual(device.status, 1)
        self.assertIs(device.is_on, True)
        self.assertIs(device.battery_ok, True)
        self.assertEqual(device.event_time, "202605152010")

    def test_parse_normal_status(self) -> None:
        msg = parse_skylinknet_message(
            '{"hub_id":"123456","data":[{"battery":1,"time":"202605152011","status":0,'
            '"dev_id":"ABCDEF12"}],"op":"report"}'
        )

        self.assertIsInstance(msg, SkylinkNetEvent)
        assert isinstance(msg, SkylinkNetEvent)
        self.assertIs(msg.devices[0].is_on, False)

    def test_websocket_url_escapes_values(self) -> None:
        self.assertEqual(
            build_websocket_url("123/456", "key with spaces"),
            "wss://api-1.skyhm.net/websock/hu/123%2F456/key%20with%20spaces",
        )

    def test_hub_stores_and_publishes_device_events(self) -> None:
        client = SkylinkNetHub("hub123", "secret", object())
        seen = []
        client.async_subscribe_device(seen.append)

        client._handle_text(
            '{"hub_id":"hub123","data":[{"battery":1,"time":"202605152010","status":1,'
            '"dev_id":"ABCDEF12"}],"op":"report"}'
        )

        self.assertIn("ABCDEF12", client.devices)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].device_id, "ABCDEF12")

    def test_hub_ignores_alarm_pseudo_device(self) -> None:
        client = SkylinkNetHub("hub123", "secret", object())
        seen = []
        client.async_subscribe_device(seen.append)

        client._handle_text(
            '{"hub_id":"hub123","data":[{"battery":1,"status":4,"dev_id":"F0000000"}],'
            '"op":"read"}'
        )

        self.assertEqual(client.devices, {})
        self.assertEqual(seen, [])
