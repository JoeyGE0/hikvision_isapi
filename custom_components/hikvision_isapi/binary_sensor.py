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
    
    # Create entities for all known events, but use channel_id from Event/triggers if available
    # Build a lookup dict: {event_id: {channel_id: EventInfo}} from supported_events
    supported_events_lookup = {}
    if supported_events:
        for event in supported_events:
            if event.id not in supported_events_lookup:
                supported_events_lookup[event.id] = {}
            supported_events_lookup[event.id][event.channel_id] = event
    
    # Create binary sensors for each camera/channel (Video Events)
    for camera in cameras:
        camera_id = camera["id"]
        camera_name = camera["name"]
        camera_serial_no = camera.get("serial_no", device_info.get("serialNumber", ""))
        camera_model = camera.get("model", device_info.get("model", ""))
        camera_firmware = camera.get("firmware", device_info.get("firmwareVersion", ""))
        
        # Create entities for all known events (not just those in Event/triggers)
        # This ensures all events are always created, even if Event/triggers doesn't return them
        for event_id, event_config in EVENTS.items():
            # Skip I/O events here - they're created at device level (channel 0)
            if event_id == EVENT_IO:
                continue
            
            # Use channel_id from Event/triggers if available, otherwise use camera_id
            event_from_triggers = None
            if event_id in supported_events_lookup:
                # Try to find event with matching channel_id
                if camera_id in supported_events_lookup[event_id]:
                    event_from_triggers = supported_events_lookup[event_id][camera_id]
                # Fallback to first available channel_id for this event
                elif supported_events_lookup[event_id]:
                    event_from_triggers = list(supported_events_lookup[event_id].values())[0]
            
            # Use channel_id from Event/triggers if available, otherwise use camera_id
            if event_from_triggers:
                channel_id = event_from_triggers.channel_id
                disabled = event_from_triggers.disabled
            else:
                channel_id = camera_id
                disabled = False
            
            # Build unique_id using device name and channel_id
            device_id_param = f"_{channel_id}" if channel_id != 0 else ""
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
                        channel_id=channel_id,
                        io_port_id=0,
                        unique_id=unique_id,
                        disabled=disabled,
                    ),
                    camera_serial_no if is_nvr else None,
                    camera_model if is_nvr else None,
                    camera_firmware if is_nvr else None,
                    nvr_device_identifier if is_nvr and camera_id > 0 else None,
                )
            )
    
    # Create channel 0 entities for I/O events (device-level)
    # Use I/O events from Event/triggers if available, otherwise create for all I/O ports
    if supported_events:
        # Use I/O events from Event/triggers
        device_io_events = [e for e in supported_events if e.id == EVENT_IO]
        for event in device_io_events:
            # I/O events are device-level (channel 0)
            device_id_param = ""  # No channel_id for I/O events
            io_port_id_param = f"_{event.io_port_id}" if event.io_port_id != 0 else "_0"
            unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{event.id}"
            
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
    else:
        # Fallback: Create default I/O entity if Event/triggers doesn't return I/O events
        device_id_param = ""  # No channel_id for I/O events
        io_port_id_param = "_0"  # Default to port 0
        unique_id = f"{device_name_slug}{device_id_param}{io_port_id_param}_{EVENT_IO}"
        
        entities.append(
            EventBinarySensor(
                coordinator,
                api,
                entry,
                host,
                device_name,
                EventInfo(
                    id=EVENT_IO,
                    channel_id=0,
                    io_port_id=0,
                    unique_id=unique_id,
                    disabled=False,
                ),
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


