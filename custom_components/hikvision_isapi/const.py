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

# Hikvision MAC address prefixes (OUI) for DHCP discovery
HIKVISION_MAC_PREFIXES: Final = [
    "00:BC:99",
    "04:03:12",
    "04:EE:CD",
    "08:3B:C1",
    "08:54:11",
    "08:A1:89",
    "08:CC:81",
    "0C:75:D2",
    "10:12:FB",
    "18:68:CB",
    "18:80:25",
    "24:0F:9B",
    "24:28:FD",
    "24:32:AE",
    "24:48:45",
    "28:57:BE",
    "2C:A5:9C",
    "34:09:62",
    "3C:1B:F8",
    "40:AC:BF",
    "44:19:B6",
    "44:47:CC",
    "44:A6:42",
    "4C:1F:86",
    "4C:62:DF",
    "4C:BD:8F",
    "4C:F5:DC",
    "50:E5:38",
    "54:8C:81",
    "54:C4:15",
    "58:03:FB",
    "58:50:ED",
    "5C:34:5B",
    "64:DB:8B",
    "68:6D:BC",
    "74:3F:C2",
    "80:48:9F",
    "80:7C:62",
    "80:BE:AF",
    "80:F5:AE",
    "84:94:59",
    "84:9A:40",
    "88:DE:39",
    "8C:E7:48",
    "94:E1:AC",
    "98:8B:0A",
    "98:9D:E5",
    "98:DF:82",
    "98:F1:12",
    "A0:FF:0C",
    "A4:14:37",
    "A4:29:02",
    "A4:4B:D9",
    "A4:A4:59",
    "A4:D5:C2",
    "AC:B9:2F",
    "AC:CB:51",
    "B4:A3:82",
    "BC:5E:33",
    "BC:9B:5E",
    "BC:AD:28",
    "BC:BA:C2",
    "C0:51:7E",
    "C0:56:E3",
    "C0:6D:ED",
    "C4:2F:90",
    "C8:A7:02",
    "D4:E8:53",
    "DC:07:F8",
    "DC:D2:6A",
    "E0:BA:AD",
    "E0:CA:3C",
    "E0:DF:13",
    "E4:D5:8B",
    "E8:A0:ED",
    "EC:A9:71",
    "EC:C8:9C",
    "F8:4D:FC",
    "FC:9F:FD",
]
