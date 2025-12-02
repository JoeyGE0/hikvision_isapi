"""Sensor platform for Hikvision ISAPI."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

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
        # System status sensors (no controls)
        HikvisionCPUUtilizationSensor(coordinator, entry, host, device_name),
        HikvisionMemoryUsageSensor(coordinator, entry, host, device_name),
        HikvisionDeviceUptimeSensor(coordinator, entry, host, device_name),
        HikvisionRebootCountSensor(coordinator, entry, host, device_name),
        HikvisionStreamingSessionsSensor(coordinator, entry, host, device_name),
        HikvisionStreamingClientsSensor(coordinator, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionCPUUtilizationSensor(SensorEntity):
    """Sensor for CPU utilization."""

    _attr_unique_id = "hikvision_cpu_utilization"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:cpu-64-bit"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        """Return the current device uptime in minutes."""
        if self.coordinator.data and "system_status" in self.coordinator.data:
            uptime_seconds = self.coordinator.data["system_status"].get("uptime")
            if uptime_seconds is not None:
                # Convert seconds from camera into whole minutes
                minutes = int(uptime_seconds / 60)
                return minutes
            return None
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "min"

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
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
            return count if count is not None else 0
        return 0

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
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

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
