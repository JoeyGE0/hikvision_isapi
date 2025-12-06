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
    for event_id, event_config in EVENTS.items():
        # Build unique_id using serial number
        serial_no = device_info.get("serialNumber", host).lower()
        device_id_param = f"_{0}" if 0 != 0 and event_id != EVENT_IO else ""
        io_port_id_param = f"_{0}" if 0 != 0 else ""
        unique_id = f"{slugify(serial_no)}{device_id_param}{io_port_id_param}_{event_id}"
        
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

    _attr_has_entity_name = True
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
        self._attr_unique_id = self.entity_id
        self._attr_translation_key = event.id
        if event.id == EVENT_IO:
            self._attr_translation_placeholders = {"io_port_id": event.io_port_id}
        
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


