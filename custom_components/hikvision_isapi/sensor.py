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
    api = data["api"]
    host = data["host"]

    entities = [
        HikvisionIRModeSensor(api, entry, host),
        HikvisionIRSensitivitySensor(api, entry, host),
        HikvisionIRFilterTimeSensor(api, entry, host),
        HikvisionLightModeSensor(api, entry, host),
    ]

    async_add_entities(entities, True)


class HikvisionIRModeSensor(SensorEntity):
    """Sensor for IR cut mode."""

    _attr_name = "IR Mode"
    _attr_unique_id = "hikvision_ir_mode_sensor"
    _attr_icon = "mdi:weather-night"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the sensor."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_ir_mode_sensor"
        self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def native_value(self):
        """Return the current IR mode."""
        return self._state

    def update(self):
        """Fetch IR mode from camera."""
        ircut_data = self.api.get_ircut_filter()
        self._state = ircut_data.get("mode", "unknown")


class HikvisionIRSensitivitySensor(SensorEntity):
    """Sensor for IR sensitivity."""

    _attr_name = "IR Sensitivity"
    _attr_unique_id = "hikvision_ir_sensitivity_sensor"
    _attr_icon = "mdi:adjust"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the sensor."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_ir_sensitivity_sensor"
        self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def native_value(self):
        """Return the current IR sensitivity."""
        return self._state

    def update(self):
        """Fetch IR sensitivity from camera."""
        ircut_data = self.api.get_ircut_filter()
        sensitivity = ircut_data.get("sensitivity")
        self._state = sensitivity if sensitivity is not None else "unknown"


class HikvisionIRFilterTimeSensor(SensorEntity):
    """Sensor for IR filter time."""

    _attr_name = "IR Filter Time"
    _attr_unique_id = "hikvision_ir_filter_time_sensor"
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the sensor."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_ir_filter_time_sensor"
        self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def native_value(self):
        """Return the current IR filter time."""
        return self._state

    def update(self):
        """Fetch IR filter time from camera."""
        ircut_data = self.api.get_ircut_filter()
        filter_time = ircut_data.get("filter_time")
        self._state = filter_time if filter_time is not None else "unknown"


class HikvisionLightModeSensor(SensorEntity):
    """Sensor for supplement light mode."""

    _attr_name = "Light Mode"
    _attr_unique_id = "hikvision_light_mode_sensor"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the sensor."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_light_mode_sensor"
        self._state = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def native_value(self):
        """Return the current light mode."""
        return self._state

    def update(self):
        """Fetch light mode from camera."""
        mode = self.api.get_supplement_light()
        self._state = mode if mode else "unknown"
