"""Binary sensor platform for Hikvision ISAPI."""
from __future__ import annotations

import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENTS
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator
from .models import EventInfo

_LOGGER = logging.getLogger(__name__)

# Event name mappings (matching your integration style)
EVENT_NAME_MAP = {
    "motiondetection": "Motion",
    "tamperdetection": "Video Tampering",
    "videoloss": "Video Loss",
    "scenechangedetection": "Scene Change",
    "fielddetection": "Intrusion",
    "linedetection": "Line Crossing",
    "regionentrance": "Region Entrance",
    "regionexiting": "Region Exiting",
}

# Event icon mappings (matching your integration style)
EVENT_ICON_MAP = {
    "motiondetection": "mdi:motion-sensor",
    "tamperdetection": "mdi:shield-alert",
    "videoloss": "mdi:video-off",
    "scenechangedetection": "mdi:image-edit",
    "fielddetection": "mdi:account-alert",
    "linedetection": "mdi:vector-line",
    "regionentrance": "mdi:sign-direction",
    "regionexiting": "mdi:exit-run",
}

# Event unique ID suffix mappings (matching your integration style)
EVENT_UNIQUE_ID_MAP = {
    "motiondetection": "motion",
    "tamperdetection": "video_tampering",
    "videoloss": "video_loss",
    "scenechangedetection": "scene_change",
    "fielddetection": "intrusion",
    "linedetection": "line_crossing",
    "regionentrance": "region_entrance",
    "regionexiting": "region_exiting",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_info = data["device_info"]
    device_name = device_info.get("deviceName", host)

    entities = []

    # Create binary sensors for all supported events (matching your naming style)
    for event_id, event_config in EVENTS.items():
        entities.append(
            EventBinarySensor(
                coordinator,
                api,
                entry,
                host,
                device_name,
                EventInfo(
                    id=event_id,
                    channel_id=0,
                ),
            )
        )

    # Also add tamper detection enabled sensor (configuration state)
    entities.append(
        HikvisionTamperDetectionBinarySensor(coordinator, api, entry, host, device_name)
    )

    async_add_entities(entities)


class EventBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Event detection sensor - matching your integration style."""

    _attr_is_on = False

    def __init__(
        self,
        coordinator: HikvisionDataUpdateCoordinator,
        api: HikvisionISAPI,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        event: EventInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self.event = event
        
        # Set name matching your integration style: "{device_name} {Event Name}"
        event_name = EVENT_NAME_MAP.get(event.id, event.id.title())
        self._attr_name = f"{device_name} {event_name}"
        
        # Set unique ID matching your integration style: "{host}_{event_name}"
        unique_id_suffix = EVENT_UNIQUE_ID_MAP.get(event.id, event.id)
        self._attr_unique_id = f"{host}_{unique_id_suffix}"
        
        # Set icon matching your integration style
        self._attr_icon = EVENT_ICON_MAP.get(event.id, "mdi:alert")
        
        # Set device class from event config
        event_config = EVENTS.get(event.id, {})
        self._attr_device_class = event_config.get("device_class")
        
        # Entity is disabled by default if event notifications aren't configured
        self._attr_entity_registry_enabled_default = not event.disabled

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class HikvisionTamperDetectionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for tamper detection enabled state (configuration)."""

    _attr_unique_id = "hikvision_tamper_detection"
    _attr_icon = "mdi:shield-alert"
    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(
        self,
        coordinator: HikvisionDataUpdateCoordinator,
        api: HikvisionISAPI,
        entry: ConfigEntry,
        host: str,
        device_name: str,
    ):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Tamper Detection Enabled"
        self._attr_unique_id = f"{host}_tamper_detection_enabled"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if tamper detection is enabled."""
        if self.coordinator.data and "tamper" in self.coordinator.data:
            return self.coordinator.data["tamper"].get("enabled", False)
        return False
