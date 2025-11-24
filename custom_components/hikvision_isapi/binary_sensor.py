"""Platform for binary sensor integration - following hikvision_next patterns."""
from __future__ import annotations

import logging
from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, EVENTS
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator
from .models import EventInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add binary sensors for hikvision events states - following hikvision_next pattern."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_info = data["device_info"]
    device_name = device_info.get("deviceName", host)
    serial_no = device_info.get("serialNumber", "").lower()
    if not serial_no:
        serial_no = slugify(device_name)

    entities = []

    # Create binary sensors for all supported events (channel 0 = main device)
    for event_id, event_config in EVENTS.items():
        device_id_param = ""  # Channel 0 for main device
        unique_id = f"{slugify(serial_no)}{device_id_param}_{event_id}"
        
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
                    unique_id=unique_id,
                ),
            )
        )

    # Also add tamper detection enabled sensor (configuration state)
    entities.append(
        HikvisionTamperDetectionBinarySensor(coordinator, api, entry, host, device_name)
    )

    async_add_entities(entities)


class EventBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Event detection sensor - following hikvision_next pattern."""

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
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self.event = event
        
        # Set entity ID and unique ID following hikvision_next pattern
        self.entity_id = ENTITY_ID_FORMAT.format(event.unique_id)
        self._attr_unique_id = event.unique_id
        
        # Set name from event config
        event_config = EVENTS.get(event.id, {})
        self._attr_name = event_config.get("label", event.id)
        
        # Set device class
        self._attr_device_class = event_config.get("device_class")
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )
        
        # Entity is disabled by default if event notifications aren't configured
        self._attr_entity_registry_enabled_default = not event.disabled

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
