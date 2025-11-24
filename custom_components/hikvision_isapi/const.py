"""Constants for Hikvision ISAPI integration."""
from typing import Final
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DOMAIN = "hikvision_isapi"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_VERIFY_SSL = "verify_ssl"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL = 30

# Webhook path for event notifications (single path for all instances)
ALARM_SERVER_PATH: Final = "/api/hikvision_isapi"

# Home Assistant event fired when camera events occur
HIKVISION_EVENT: Final = f"{DOMAIN}_event"

# Event type mappings (matching hikvision_next patterns)
EVENT_BASIC: Final = "basic"
EVENT_SMART: Final = "smart"

EVENTS: Final = {
    "motiondetection": {
        "type": EVENT_BASIC,
        "label": "Motion",
        "slug": "motionDetection",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
    "tamperdetection": {
        "type": EVENT_BASIC,
        "label": "Video Tampering",
        "slug": "tamperDetection",
        "device_class": BinarySensorDeviceClass.TAMPER,
    },
    "videoloss": {
        "type": EVENT_BASIC,
        "label": "Video Loss",
        "slug": "videoLoss",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "scenechangedetection": {
        "type": EVENT_SMART,
        "label": "Scene Change",
        "slug": "SceneChangeDetection",
        "device_class": BinarySensorDeviceClass.TAMPER,
    },
    "fielddetection": {
        "type": EVENT_SMART,
        "label": "Intrusion",
        "slug": "FieldDetection",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
    "linedetection": {
        "type": EVENT_SMART,
        "label": "Line Crossing",
        "slug": "LineDetection",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
    "regionentrance": {
        "type": EVENT_SMART,
        "label": "Region Entrance",
        "slug": "regionEntrance",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
    "regionexiting": {
        "type": EVENT_SMART,
        "label": "Region Exiting",
        "slug": "regionExiting",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
}

# Alternate event IDs (some cameras use different names)
EVENTS_ALTERNATE_ID: Final = {
    "vmd": "motiondetection",
    "thermometry": "motiondetection",
    "shelteralarm": "tamperdetection",
    "VMDHumanVehicle": "motiondetection",
}
