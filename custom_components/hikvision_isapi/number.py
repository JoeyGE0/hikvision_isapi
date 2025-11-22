"""Number platform for Hikvision ISAPI."""
import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up number entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionIRSensitivityNumber(coordinator, api, entry, host, device_name),
        HikvisionIRFilterTimeNumber(coordinator, api, entry, host, device_name),
        HikvisionSpeakerVolumeNumber(coordinator, api, entry, host, device_name),
        HikvisionMicrophoneVolumeNumber(coordinator, api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionIRSensitivityNumber(NumberEntity):
    """Number entity for IR sensitivity."""

    _attr_unique_id = "hikvision_ir_sensitivity"
    _attr_native_min_value = 0
    _attr_native_max_value = 7
    _attr_native_step = 1
    _attr_icon = "mdi:adjust"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} IR Sensitivity"
        self._attr_unique_id = f"{host}_ir_sensitivity"
        self._optimistic_value = None

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
    def native_value(self) -> float | None:
        """Return the current value."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data
        if self.coordinator.data and "ircut" in self.coordinator.data:
            sensitivity = self.coordinator.data["ircut"].get("sensitivity")
            if sensitivity is not None:
                return float(sensitivity)
        return None

    async def async_set_native_value(self, value: float):
        """Set the value."""
        # Optimistic update - show immediately
        self._optimistic_value = float(value)
        self.async_write_ha_state()
        
        # Send to device
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_sensitivity, int(value)
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("ircut", {}).get("sensitivity") == int(value)):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIRFilterTimeNumber(NumberEntity):
    """Number entity for IR filter time."""

    _attr_unique_id = "hikvision_ir_filter_time"
    _attr_native_min_value = 5
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} IR Filter Time"
        self._attr_unique_id = f"{host}_ir_filter_time"
        self._optimistic_value = None

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
    def native_value(self) -> float | None:
        """Return the current value."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data
        if self.coordinator.data and "ircut" in self.coordinator.data:
            filter_time = self.coordinator.data["ircut"].get("filter_time")
            if filter_time is not None:
                return float(filter_time)
        return None

    async def async_set_native_value(self, value: float):
        """Set the value."""
        # Optimistic update - show immediately
        self._optimistic_value = float(value)
        self.async_write_ha_state()
        
        # Send to device
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_filter_time, int(value)
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("ircut", {}).get("filter_time") == int(value)):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionSpeakerVolumeNumber(NumberEntity):
    """Number entity for speaker volume."""

    _attr_unique_id = "hikvision_speaker_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Speaker Volume"
        self._attr_unique_id = f"{host}_speaker_volume"
        self._optimistic_value = None

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
    def native_value(self) -> float | None:
        """Return the current value."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("speakerVolume")
            if volume is not None:
                return float(volume)
        return None

    async def async_set_native_value(self, value: float):
        """Set the value."""
        # Optimistic update - show immediately
        self._optimistic_value = float(value)
        self.async_write_ha_state()
        
        # Send to device
        success = await self.hass.async_add_executor_job(
            self.api.set_speaker_volume, int(value)
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("audio", {}).get("speakerVolume") == int(value)):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionMicrophoneVolumeNumber(NumberEntity):
    """Number entity for microphone volume."""

    _attr_unique_id = "hikvision_microphone_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_icon = "mdi:microphone"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Mic Volume"
        self._attr_unique_id = f"{host}_microphone_volume"
        self._optimistic_value = None

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
    def native_value(self) -> float | None:
        """Return the current value."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("microphoneVolume")
            if volume is not None:
                return float(volume)
        return None

    async def async_set_native_value(self, value: float):
        """Set the value."""
        # Optimistic update - show immediately
        self._optimistic_value = float(value)
        self.async_write_ha_state()
        
        # Send to device
        success = await self.hass.async_add_executor_job(
            self.api.set_microphone_volume, int(value)
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("audio", {}).get("microphoneVolume") == int(value)):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

