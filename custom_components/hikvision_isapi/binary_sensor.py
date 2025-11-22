"""Binary sensor platform for Hikvision ISAPI."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up binary sensor entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionMotionDetectionBinarySensor(coordinator, api, entry, host, device_name),
        HikvisionTamperDetectionBinarySensor(coordinator, api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionMotionDetectionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for motion detection enabled state."""

    _attr_unique_id = "hikvision_motion_detection"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Motion Detection"
        self._attr_unique_id = f"{host}_motion_detection"

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
        """Return if motion detection is enabled."""
        if self.coordinator.data and "motion" in self.coordinator.data:
            return self.coordinator.data["motion"].get("enabled", False)
        return False


class HikvisionTamperDetectionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for tamper detection enabled state."""

    _attr_unique_id = "hikvision_tamper_detection"
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Tamper Detection"
        self._attr_unique_id = f"{host}_tamper_detection"

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

