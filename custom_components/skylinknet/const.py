"""Constants for the SkylinkNet integration."""

from __future__ import annotations

DOMAIN = "skylinknet"
NAME = "SkylinkNet"

CONF_HUB_ID = "hub_id"
CONF_HUB_KEY = "hub_key"
CONF_DEFAULT_DEVICE_CLASS = "default_device_class"

DEFAULT_DEVICE_CLASS = "motion"
DEVICE_CLASS_NONE = "none"

PLATFORMS = ["binary_sensor"]

ALARM_DEVICE_ID = "F0000000"

ATTR_RAW_STATUS = "raw_status"
ATTR_BATTERY_OK = "battery_ok"
ATTR_EVENT_TIME = "event_time"
ATTR_DEVICE_ID = "device_id"
