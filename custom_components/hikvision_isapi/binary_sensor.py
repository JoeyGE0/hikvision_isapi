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
    supported_events = data.get("supported_events", [])
    nvr_device_identifier = data.get("nvr_device_identifier", host)
    device_name = device_info.get("deviceName", host)
    is_nvr = capabilities.get("is_nvr", False)

    entities = []
    device_name_slug = slugify(device_name.lower())
    
    # Create binary sensors for each camera/channel (Video Events)
    # Only create entities for events actually returned by Event/triggers
    for camera in cameras:
        camera_id = camera["id"]
        camera_name = camera["name"]
        camera_serial_no = camera.get("serial_no", device_info.get("serialNumber", ""))
        camera_model = camera.get("model", device_info.get("model", ""))
        camera_firmware = camera.get("firmware", device_info.get("firmwareVersion", ""))
        
        # Only create entities for events in supported_events that match this camera's channel_id
        # Only create entities for events the camera actually supports
        for event in supported_events:
            # Skip I/O events here - they're created at device level (channel 0)
            if event.id == EVENT_IO:
                continue
            
            # Only create entity if event matches this camera's channel_id
            if event.channel_id == camera_id:
                # Build unique_id for channel-specific events (must match notifications.py format)
                # Format: {device_name_slug}_{channel_id}_{event_id}
                device_id_param = f"_{event.channel_id}" if event.channel_id != 0 else ""
                io_port_id_param = ""  # Non-I/O events don't include io_port_id
                unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{event.id}"
                
                # Update event's unique_id if not already set
                if not event.unique_id:
                    event.unique_id = unique_id
                
                entities.append(
                    EventBinarySensor(
                        coordinator,
                        api,
                        entry,
                        host,
                        camera_name if is_nvr or len(cameras) > 1 else device_name,
                        event,
                        camera_serial_no if is_nvr else None,
                        camera_model if is_nvr else None,
                        camera_firmware if is_nvr else None,
                        nvr_device_identifier if is_nvr and camera_id > 0 else None,
                    )
                )
    
    # Create channel 0 entities (device-level events)
    # Only create entities for events in supported_events with channel_id=0
    for event in supported_events:
        if event.channel_id == 0:
            # Build unique_id for channel 0 events
            device_id_param = ""  # No channel_id for device-level events
            # For I/O events: always include io_port_id (even if 0) to match notifications.py format
            # For other events: don't include io_port_id (should be 0 anyway)
            if event.id == EVENT_IO:
                io_port_id_param = f"_{event.io_port_id}"  # I/O events always include io_port_id
            else:
                io_port_id_param = ""  # Non-I/O events don't include io_port_id
            unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{event.id}"
            
            # Update event's unique_id if not already set
            if not event.unique_id:
                event.unique_id = unique_id
            
            entities.append(
                EventBinarySensor(
                    coordinator,
                    api,
                    entry,
                    host,
                    device_name,
                    event,
                    None,  # No camera serial for device-level events
                    None,  # No camera model for device-level events
                    None,  # No camera firmware for device-level events
                    None,  # No via_device for device-level events
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
        camera_serial_no: str | None = None,
        camera_model: str | None = None,
        camera_firmware: str | None = None,
        nvr_device_identifier: str | None = None,
    ) -> None:
        """Initialize."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self.event = event
        
        # Set entity_id and unique_id
        # Ensure unique_id is set (should be set before creating entity, but check for safety)
        if not event.unique_id:
            # Fallback: build unique_id if somehow not set (must match notifications.py format)
            device_name_slug = slugify(device_name.lower())
            if event.id == EVENT_IO:
                device_id_param = ""
                io_port_id_param = f"_{event.io_port_id}"  # I/O events always include io_port_id
            else:
                device_id_param = f"_{event.channel_id}" if event.channel_id != 0 else ""
                io_port_id_param = ""  # Non-I/O events don't include io_port_id
            event.unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{event.id}"
        
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
        
        # Set icons based on event type (dynamic based on state)
        if event.id == "videoloss":
            # Video Loss: ethernet-cable (on) / ethernet-cable-off (off)
            self._icon_on = "mdi:ethernet-cable"
            self._icon_off = "mdi:ethernet-cable-off"
        elif event.id in ("tamperdetection", "scenechangedetection"):
            # Tamper and Scene Change: alarm-light (on) / alarm-light-off (off)
            self._icon_on = "mdi:alarm-light"
            self._icon_off = "mdi:alarm-light-off"
        else:
            self._icon_on = None
            self._icon_off = None
        
        # Get device info for entity
        data = coordinator.hass.data[DOMAIN][entry.entry_id]
        device_info = data["device_info"]
        
        # Determine device identifier - use camera serial if available (NVR), otherwise device serial/host
        if camera_serial_no:
            device_identifier = camera_serial_no
        else:
            device_identifier = device_info.get("serialNumber") or host
        
        # Build device info with full details
        device_info_dict = {
            "identifiers": {(DOMAIN, device_identifier)},
            "manufacturer": device_info.get("manufacturer", "Hikvision").title(),
            "model": camera_model or device_info.get("model", "Hikvision Camera"),
            "name": device_name,
            "sw_version": camera_firmware or device_info.get("firmwareVersion"),
        }
        
        # Add via_device for NVR cameras (camera_id > 0 on NVR)
        if nvr_device_identifier:
            device_info_dict["via_device"] = (DOMAIN, nvr_device_identifier)
        
        self._attr_device_info = DeviceInfo(**device_info_dict)
        
        # Entity is disabled by default if event notifications aren't configured
        self._attr_entity_registry_enabled_default = not event.disabled

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    @property
    def icon(self) -> str | None:
        """Return the icon based on state."""
        if hasattr(self, '_icon_on') and hasattr(self, '_icon_off'):
            if self._icon_on and self._icon_off:
                # Use _attr_is_on to check state (True = ON, False = OFF)
                return self._icon_on if self._attr_is_on else self._icon_off
        return None


