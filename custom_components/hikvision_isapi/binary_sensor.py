"""Binary sensor platform for Hikvision ISAPI."""
from __future__ import annotations

import logging
from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN, EVENTS, EVENT_IO
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator
from .models import EventInfo

_LOGGER = logging.getLogger(__name__)


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

    # Create binary sensors for all supported events
    # Use channel 1 as default (matching API channel)
    channel_id = api.channel
    
    # Map event_id to unique_id suffix (matching your original naming convention)
    event_unique_id_map = {
        "motiondetection": "motion",
        "tamperdetection": "video_tampering",
        "videoloss": "video_loss",
        "scenechangedetection": "scene_change",
        "fielddetection": "intrusion",
        "linedetection": "line_crossing",
        "regionentrance": "region_entrance",
        "regionexiting": "region_exiting",
    }
    
    for event_id, event_config in EVENTS.items():
        # Build unique_id using host (matching your original format)
        unique_id_suffix = event_unique_id_map.get(event_id, event_id)
        unique_id = f"{host}_{unique_id_suffix}"
        
        entities.append(
            EventBinarySensor(
                coordinator,
                api,
                entry,
                host,
                device_name,
                EventInfo(
                    id=event_id,
                    channel_id=channel_id,
                    io_port_id=0,
                    unique_id=unique_id,
                ),
            )
        )

    async_add_entities(entities)


class EventBinarySensor(BinarySensorEntity):
    """Event detection sensor."""

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
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self.event = event
        
        # Set unique_id (entity_id will be auto-generated from name)
        self._attr_unique_id = event.unique_id
        
        # Set name for auto-generated entity_id (matching your naming convention)
        event_name_map = {
            "motiondetection": "Motion",
            "tamperdetection": "Video Tampering",
            "videoloss": "Video Loss",
            "scenechangedetection": "Scene Change",
            "fielddetection": "Intrusion",
            "linedetection": "Line Crossing",
            "regionentrance": "Region Entrance",
            "regionexiting": "Region Exiting",
        }
        event_name = event_name_map.get(event.id, event.id.title())
        self._attr_name = f"{device_name} {event_name}"
        
        # Set device class from event config
        event_config = EVENTS.get(event.id, {})
        self._attr_device_class = event_config.get("device_class")
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )
        
        # Entity is disabled by default if event notifications aren't configured
        self._attr_entity_registry_enabled_default = not event.disabled

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


