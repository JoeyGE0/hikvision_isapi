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
        HikvisionSpeakerVolumeSensor(coordinator, entry, host, device_name),
        HikvisionMicrophoneVolumeSensor(coordinator, entry, host, device_name),
        HikvisionLEDOnDurationSensor(coordinator, entry, host, device_name),
        HikvisionCPUUtilizationSensor(coordinator, entry, host, device_name),
        HikvisionMemoryUsageSensor(coordinator, entry, host, device_name),
        HikvisionDeviceUptimeSensor(coordinator, entry, host, device_name),
        HikvisionRebootCountSensor(coordinator, entry, host, device_name),
        HikvisionStreamingSessionsSensor(coordinator, entry, host, device_name),
        HikvisionStreamingClientsSensor(coordinator, entry, host, device_name),
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
        self._attr_name = f"{device_name} Day/Night Switch Sensitivity"
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
        self._attr_name = f"{device_name} Day/Night Switch Delay"
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
        if self.coordinator.data and "supplement_light" in self.coordinator.data:
            api_value = self.coordinator.data["supplement_light"].get("mode")
            return api_to_display.get(api_value, api_value if api_value else "unknown")
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionSpeakerVolumeSensor(SensorEntity):
    """Sensor for speaker volume."""

    _attr_unique_id = "hikvision_speaker_volume_sensor"
    _attr_icon = "mdi:volume-high"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Speaker Volume"
        self._attr_unique_id = f"{host}_speaker_volume_sensor"

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
        """Return the current speaker volume."""
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("speakerVolume")
            return volume if volume is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionMicrophoneVolumeSensor(SensorEntity):
    """Sensor for microphone volume."""

    _attr_unique_id = "hikvision_microphone_volume_sensor"
    _attr_icon = "mdi:microphone"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Mic Volume"
        self._attr_unique_id = f"{host}_microphone_volume_sensor"

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
        """Return the current microphone volume."""
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("microphoneVolume")
            return volume if volume is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionLEDOnDurationSensor(SensorEntity):
    """Sensor for LED on duration."""

    _attr_unique_id = "hikvision_led_on_duration_sensor"
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} LED On Duration"
        self._attr_unique_id = f"{host}_led_on_duration_sensor"

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
        """Return the current LED on duration."""
        if self.coordinator.data and "white_light_time" in self.coordinator.data:
            duration = self.coordinator.data["white_light_time"]
            return duration if duration is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionCPUUtilizationSensor(SensorEntity):
    """Sensor for CPU utilization."""

    _attr_unique_id = "hikvision_cpu_utilization"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:cpu-64-bit"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} CPU Utilization"
        self._attr_unique_id = f"{host}_cpu_utilization"

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
        """Return the current CPU utilization."""
        if self.coordinator.data and "system_status" in self.coordinator.data:
            cpu = self.coordinator.data["system_status"].get("cpu_utilization")
            return cpu if cpu is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionMemoryUsageSensor(SensorEntity):
    """Sensor for memory usage."""

    _attr_unique_id = "hikvision_memory_usage"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:memory"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Memory Usage"
        self._attr_unique_id = f"{host}_memory_usage"

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
        """Return the current memory usage."""
        if self.coordinator.data and "system_status" in self.coordinator.data:
            memory = self.coordinator.data["system_status"].get("memory_usage")
            return memory if memory is not None else "unknown"
        return "unknown"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionDeviceUptimeSensor(SensorEntity):
    """Sensor for device uptime."""

    _attr_unique_id = "hikvision_device_uptime"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Device Uptime"
        self._attr_unique_id = f"{host}_device_uptime"

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
        """Return the current device uptime in hours."""
        if self.coordinator.data and "system_status" in self.coordinator.data:
            uptime_seconds = self.coordinator.data["system_status"].get("uptime")
            if uptime_seconds is not None:
                hours = uptime_seconds / 3600
                if hours >= 24:
                    days = int(hours / 24)
                    remaining_hours = int(hours % 24)
                    return f"{days}d {remaining_hours}h"
                else:
                    return f"{int(hours)}h"
            return "unknown"
        return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionStreamingSessionsSensor(SensorEntity):
    """Sensor for total streaming sessions."""

    _attr_unique_id = "hikvision_streaming_sessions"
    _attr_icon = "mdi:play-network"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Active Streaming Sessions"
        self._attr_unique_id = f"{host}_streaming_sessions"

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
        """Return the total streaming sessions count."""
        if self.coordinator.data and "streaming_status" in self.coordinator.data:
            count = self.coordinator.data["streaming_status"].get("totalStreamingSessions")
            return count if count is not None else "unknown"
        return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionStreamingClientsSensor(SensorEntity):
    """Sensor for streaming client addresses."""

    _attr_unique_id = "hikvision_streaming_clients"
    _attr_icon = "mdi:account-network"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Streaming Clients"
        self._attr_unique_id = f"{host}_streaming_clients"

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
        """Return the client addresses."""
        if self.coordinator.data and "streaming_status" in self.coordinator.data:
            clients = self.coordinator.data["streaming_status"].get("clientAddresses")
            return clients if clients is not None else "None"
        return "None"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionRebootCountSensor(SensorEntity):
    """Sensor for total reboot count."""

    _attr_unique_id = "hikvision_reboot_count"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Total Reboots"
        self._attr_unique_id = f"{host}_reboot_count"

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
        """Return the total reboot count."""
        if self.coordinator.data and "system_status" in self.coordinator.data:
            count = self.coordinator.data["system_status"].get("reboot_count")
            return count if count is not None else "unknown"
        return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
