"""Binary sensor platform for Hikvision ISAPI."""
from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENTS, HIKVISION_EVENT
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator
from .models import EventInfo

_LOGGER = logging.getLogger(__name__)

# Auto-clear timeout for event sensors (5 seconds default, like hikvision_next)
EVENT_CLEAR_TIMEOUT = timedelta(seconds=5)

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


class EventBinarySensor(BinarySensorEntity):
    """Event detection sensor - reads from state set by webhook handler (like hikvision_next)."""

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
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self.event = event
        self._hass = None
        self._clear_timer = None
        self._state = False
        
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

    @property
    def is_on(self) -> bool:
        """Return if the sensor is on (event detected)."""
        return self._state

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self._hass = self.hass
        
        # Listen to Hikvision events (fired by webhook handler)
        @callback
        def hikvision_event_listener(event: Event) -> None:
            """Handle Hikvision events from webhook."""
            event_id = event.data.get("event_id", "")
            # Match event ID (handle both exact match and alternate names)
            if event_id == self.event.id or event_id.lower() == self.event.id.lower():
                self._state = True
                self.async_write_ha_state()
                
                # Auto-clear after timeout (like hikvision_next)
                if self._clear_timer:
                    self._clear_timer()
                
                def clear_state(_now):
                    self._state = False
                    self.async_write_ha_state()
                
                self._clear_timer = self.hass.loop.call_later(
                    EVENT_CLEAR_TIMEOUT.total_seconds(),
                    clear_state
                )
        
        self.async_on_remove(
            self.hass.bus.async_listen(HIKVISION_EVENT, hikvision_event_listener)
        )


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
