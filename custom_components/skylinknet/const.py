"""Constants for the SkylinkNet integration."""

from __future__ import annotations

DOMAIN = "skylinknet"
NAME = "SkylinkNet"

CONF_HUB_ID = "hub_id"
CONF_HUB_KEY = "hub_key"
CONF_DEFAULT_DEVICE_CLASS = "default_device_class"
CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_IGNORE_FUTURE_EVENTS = "ignore_future_events"
CONF_SKYLINKNET_DEVICE_ID = "skylinknet_device_id"

DEFAULT_DEVICE_CLASS = "motion"
DEVICE_CLASS_NONE = "none"

PLATFORMS = ["binary_sensor"]

SERVICE_FORGET_DEVICE = "forget_device"
SERVICE_ALLOW_DEVICE = "allow_device"

ALARM_DEVICE_ID = "F0000000"

ATTR_RAW_STATUS = "raw_status"
ATTR_BATTERY_OK = "battery_ok"
ATTR_EVENT_TIME = "event_time"
ATTR_DEVICE_ID = "device_id"
