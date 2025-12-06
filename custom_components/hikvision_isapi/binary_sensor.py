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
    cameras = data.get("cameras", [])
    capabilities = data.get("capabilities", {})
    device_name = device_info.get("deviceName", host)
    is_nvr = capabilities.get("is_nvr", False)

    entities = []
    device_name_slug = slugify(device_name.lower())
    
    # Create binary sensors for each camera/channel
    for camera in cameras:
        camera_id = camera["id"]
        camera_name = camera["name"]
        
        for event_id, event_config in EVENTS.items():
            # Build unique_id using device name and camera_id
            # For I/O events: no channel_id, but include io_port_id (even if 0 for now)
            # For other events: include channel_id if != 0, io_port_id only if != 0
            device_id_param = f"_{camera_id}" if camera_id != 0 and event_id != EVENT_IO else ""
            # For I/O events, io_port_id is part of the unique_id (even if 0)
            # For other events, only include io_port_id if non-zero (should be 0 normally)
            if event_id == EVENT_IO:
                io_port_id_param = "_0"  # I/O events always include io_port_id (even if 0)
            else:
                io_port_id_param = ""  # Non-I/O events don't include io_port_id (should be 0)
            unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{event_id}"
            
            entities.append(
                EventBinarySensor(
                    coordinator,
                    api,
                    entry,
                    host,
                    camera_name if is_nvr or len(cameras) > 1 else device_name,
                    EventInfo(
                        id=event_id,
                        channel_id=camera_id,
                        io_port_id=0,
                        unique_id=unique_id,
                    ),
                )
            )
    
    # Also create general events (channel 0) for NVR-level events
    if is_nvr:
        for event_id, event_config in EVENTS.items():
            if event_id == EVENT_IO:  # I/O events are per-port, not general
                continue
            unique_id = f"{device_name_slug}_{event_id}"
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
        
        # Set entity_id and unique_id
        self.entity_id = ENTITY_ID_FORMAT.format(event.unique_id)
        self._attr_unique_id = event.unique_id  # Store just the identifier, not full entity_id
        
        # Set name using device name + event label (like switches do)
        event_config = EVENTS.get(event.id, {})
        event_label = event_config.get("label", event.id.title())
        if event.id == EVENT_IO:
            self._attr_name = f"{device_name} Alarm Input {event.io_port_id}"
        else:
            self._attr_name = f"{device_name} {event_label}"
        
        # Set device class from event config
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


