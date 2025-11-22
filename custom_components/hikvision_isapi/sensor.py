"""Sensor platform for Hikvision ISAPI."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up sensors for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionIRModeSensor(coordinator, entry, host, device_name),
        HikvisionIRSensitivitySensor(coordinator, entry, host, device_name),
        HikvisionIRFilterTimeSensor(coordinator, entry, host, device_name),
        HikvisionLightModeSensor(coordinator, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionIRModeSensor(SensorEntity):
    """Sensor for IR cut mode."""

    _attr_unique_id = "hikvision_ir_mode_sensor"
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Day/Night Switch"
        self._attr_unique_id = f"{host}_ir_mode_sensor"

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
    def native_value(self):
        """Return the current IR mode."""
        # Map API values to display names
        api_to_display = {
            "day": "Day",
            "night": "Night",
            "auto": "Auto"
        }
        if self.coordinator.data and "ircut" in self.coordinator.data:
            api_value = self.coordinator.data["ircut"].get("mode", "unknown")
            return api_to_display.get(api_value, api_value)
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIRSensitivitySensor(SensorEntity):
    """Sensor for IR sensitivity."""

    _attr_unique_id = "hikvision_ir_sensitivity_sensor"
    _attr_icon = "mdi:adjust"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} IR Sensitivity"
        self._attr_unique_id = f"{host}_ir_sensitivity_sensor"

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
    def native_value(self):
        """Return the current IR sensitivity."""
        if self.coordinator.data and "ircut" in self.coordinator.data:
            sensitivity = self.coordinator.data["ircut"].get("sensitivity")
            return sensitivity if sensitivity is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIRFilterTimeSensor(SensorEntity):
    """Sensor for IR filter time."""

    _attr_unique_id = "hikvision_ir_filter_time_sensor"
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} IR Filter Time"
        self._attr_unique_id = f"{host}_ir_filter_time_sensor"

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
    def native_value(self):
        """Return the current IR filter time."""
        if self.coordinator.data and "ircut" in self.coordinator.data:
            filter_time = self.coordinator.data["ircut"].get("filter_time")
            return filter_time if filter_time is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionLightModeSensor(SensorEntity):
    """Sensor for supplement light mode."""

    _attr_unique_id = "hikvision_light_mode_sensor"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Supplement Light"
        self._attr_unique_id = f"{host}_light_mode_sensor"

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
    def native_value(self):
        """Return the current light mode."""
        # Map API values to display names
        api_to_display = {
            "eventIntelligence": "Smart",
            "irLight": "IR Supplement Light",
            "close": "Off"
        }
        if self.coordinator.data and "light_mode" in self.coordinator.data:
            api_value = self.coordinator.data["light_mode"]
            return api_to_display.get(api_value, api_value if api_value else "unknown")
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
