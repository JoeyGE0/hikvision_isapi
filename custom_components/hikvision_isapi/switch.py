"""Switch platform for Hikvision ISAPI."""
from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_helpers import get_primary_device_info, alarm_output_data_key
from .api import HikvisionISAPI, EventMutexError
from .coordinator import HikvisionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def _async_sync_alarm_input_state(
    coordinator: HikvisionDataUpdateCoordinator,
    hass: HomeAssistant,
    api: HikvisionISAPI,
    port_id: int = 1,
) -> bool | None:
    """Read alarm input config from camera and merge into coordinator (no full refresh)."""
    result = await hass.async_add_executor_job(api.get_alarm_input, port_id)
    if not result or "enabled" not in result:
        return None
    if coordinator.data is not None:
        coordinator.data["alarm_input"] = result
    return bool(result["enabled"])


async def _async_sync_alarm_output_state(
    coordinator: HikvisionDataUpdateCoordinator,
    hass: HomeAssistant,
    api: HikvisionISAPI,
    data_key: str,
    port_id: int = 1,
) -> bool | None:
    """Read alarm output relay state from camera and merge into coordinator."""
    result = await hass.async_add_executor_job(api.get_alarm_output, port_id)
    if not result or "enabled" not in result:
        return None
    enabled = bool(result["enabled"])
    if coordinator.data is not None:
        coordinator.data[data_key] = enabled
    return enabled


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up switch entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)
    detected_features = data.get("detected_features", {})

    entities = []
    
    # Only add entities if their features are detected
    if detected_features.get("noise_reduce", False):
        entities.append(HikvisionNoiseReduceSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("motion_detection", False):
        entities.append(HikvisionMotionDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("tamper_detection", False):
        entities.append(HikvisionTamperDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("intrusion_detection", False):
        entities.append(HikvisionIntrusionDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("line_crossing_detection", False):
        entities.append(HikvisionLineCrossingDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("scene_change_detection", False):
        entities.append(HikvisionSceneChangeDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("defocus_detection", False):
        entities.append(HikvisionDefocusDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("region_entrance_detection", False):
        entities.append(HikvisionRegionEntranceDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("region_exiting_detection", False):
        entities.append(HikvisionRegionExitingDetectionSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("alarm_input", False):
        entities.append(HikvisionAlarmInputSwitch(coordinator, api, entry, host, device_name))
    if detected_features.get("alarm_output", False):
        entities.append(HikvisionAlarmOutputSwitch(coordinator, api, entry, host, device_name, 1))

    async_add_entities(entities)


class HikvisionNoiseReduceSwitch(SwitchEntity):
    """Switch entity for noise reduction."""

    _attr_unique_id = "hikvision_noisereduce"
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Noise Reduction"
        self._attr_unique_id = f"{host}_noisereduce"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if noise reduction is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "audio" in self.coordinator.data:
            return self.coordinator.data["audio"].get("noisereduce", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on noise reduction."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_noisereduce, True
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("audio", {}).get("noisereduce") == True):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_turn_off(self, **kwargs):
        """Turn off noise reduction."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_noisereduce, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("audio", {}).get("noisereduce") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionMotionDetectionSwitch(SwitchEntity):
    """Switch entity for motion detection control."""

    _attr_unique_id = "hikvision_motion_detection"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Motion Detection"
        self._attr_unique_id = f"{host}_motion_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if motion detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "motion" in self.coordinator.data:
            return self.coordinator.data["motion"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on motion detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_motion_detection, True
            )
            
            if success:
                await self.coordinator.async_request_refresh()
                if (self.coordinator.data and 
                    self.coordinator.data.get("motion", {}).get("enabled") == True):
                    self._optimistic_value = None
            else:
                self._optimistic_value = None
        except EventMutexError as e:
            self._optimistic_value = None
            _LOGGER.error("Cannot enable motion detection: %s", e.message)
            # Show error to user via Home Assistant's error system
            raise

    async def async_turn_off(self, **kwargs):
        """Turn off motion detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_motion_detection, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("motion", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionTamperDetectionSwitch(SwitchEntity):
    """Switch entity for tamper detection control."""

    _attr_unique_id = "hikvision_tamper_detection"
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Video Tampering Detection"
        self._attr_unique_id = f"{host}_tamper_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if tamper detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "tamper" in self.coordinator.data:
            return self.coordinator.data["tamper"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on tamper detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_tamper_detection, True
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("tamper", {}).get("enabled") == True):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_turn_off(self, **kwargs):
        """Turn off tamper detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_tamper_detection, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("tamper", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIntrusionDetectionSwitch(SwitchEntity):
    """Switch entity for intrusion detection control."""

    _attr_unique_id = "hikvision_intrusion_detection"
    _attr_icon = "mdi:account-alert"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Intrusion Detection"
        self._attr_unique_id = f"{host}_intrusion_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if intrusion detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "field_detection" in self.coordinator.data:
            return self.coordinator.data["field_detection"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on intrusion detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_field_detection, True
            )
            
            if success:
                await self.coordinator.async_request_refresh()
                if (self.coordinator.data and 
                    self.coordinator.data.get("field_detection", {}).get("enabled") == True):
                    self._optimistic_value = None
            else:
                self._optimistic_value = None
        except EventMutexError as e:
            self._optimistic_value = None
            _LOGGER.error("Cannot enable intrusion detection: %s", e.message)
            raise

    async def async_turn_off(self, **kwargs):
        """Turn off intrusion detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_field_detection, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("field_detection", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionLineCrossingDetectionSwitch(SwitchEntity):
    """Switch entity for line crossing detection control."""

    _attr_unique_id = "hikvision_line_crossing_detection"
    _attr_icon = "mdi:vector-line"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Line Crossing Detection"
        self._attr_unique_id = f"{host}_line_crossing_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if line crossing detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "line_detection" in self.coordinator.data:
            return self.coordinator.data["line_detection"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on line crossing detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_line_detection, True
            )
            
            if success:
                await self.coordinator.async_request_refresh()
                if (self.coordinator.data and 
                    self.coordinator.data.get("line_detection", {}).get("enabled") == True):
                    self._optimistic_value = None
            else:
                self._optimistic_value = None
        except EventMutexError as e:
            self._optimistic_value = None
            _LOGGER.error("Cannot enable line crossing detection: %s", e.message)
            raise

    async def async_turn_off(self, **kwargs):
        """Turn off line crossing detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_line_detection, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("line_detection", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionSceneChangeDetectionSwitch(SwitchEntity):
    """Switch entity for scene change detection control."""

    _attr_unique_id = "hikvision_scene_change_detection"
    _attr_icon = "mdi:image-edit"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Scene Change Detection"
        self._attr_unique_id = f"{host}_scene_change_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if scene change detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "scene_change" in self.coordinator.data:
            return self.coordinator.data["scene_change"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on scene change detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_scene_change_detection, True
            )
            
            if success:
                await self.coordinator.async_request_refresh()
                if (self.coordinator.data and 
                    self.coordinator.data.get("scene_change", {}).get("enabled") == True):
                    self._optimistic_value = None
            else:
                self._optimistic_value = None
        except EventMutexError as e:
            self._optimistic_value = None
            _LOGGER.error("Cannot enable scene change detection: %s", e.message)
            raise

    async def async_turn_off(self, **kwargs):
        """Turn off scene change detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_scene_change_detection, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("scene_change", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionDefocusDetectionSwitch(SwitchEntity):
    """Switch entity for defocus detection control."""

    _attr_unique_id = "hikvision_defocus_detection"
    _attr_icon = "mdi:image-filter-center-focus"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Defocus Detection"
        self._attr_unique_id = f"{host}_defocus_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if defocus detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        if not self.available:
            return None

        if self.coordinator.data and "defocus" in self.coordinator.data:
            return self.coordinator.data["defocus"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on defocus detection."""
        self._optimistic_value = True
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_defocus_detection, True
        )

        if success:
            await self.coordinator.async_request_refresh()
            if (
                self.coordinator.data
                and self.coordinator.data.get("defocus", {}).get("enabled") is True
            ):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_turn_off(self, **kwargs):
        """Turn off defocus detection."""
        self._optimistic_value = False
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_defocus_detection, False
        )

        if success:
            await self.coordinator.async_request_refresh()
            if (
                self.coordinator.data
                and self.coordinator.data.get("defocus", {}).get("enabled") is False
            ):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionRegionEntranceDetectionSwitch(SwitchEntity):
    """Switch entity for region entrance detection control."""

    _attr_unique_id = "hikvision_region_entrance_detection"
    _attr_icon = "mdi:sign-direction"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Region Entrance Detection"
        self._attr_unique_id = f"{host}_region_entrance_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if region entrance detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "region_entrance" in self.coordinator.data:
            return self.coordinator.data["region_entrance"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on region entrance detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_region_entrance, True
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("region_entrance", {}).get("enabled") == True):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_turn_off(self, **kwargs):
        """Turn off region entrance detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_region_entrance, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("region_entrance", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionRegionExitingDetectionSwitch(SwitchEntity):
    """Switch entity for region exiting detection control."""

    _attr_unique_id = "hikvision_region_exiting_detection"
    _attr_icon = "mdi:exit-run"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Region Exiting Detection"
        self._attr_unique_id = f"{host}_region_exiting_detection"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if region exiting detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if not self.available:
            return None
        
        if self.coordinator.data and "region_exiting" in self.coordinator.data:
            return self.coordinator.data["region_exiting"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on region exiting detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_region_exiting, True
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("region_exiting", {}).get("enabled") == True):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_turn_off(self, **kwargs):
        """Turn off region exiting detection."""
        self._optimistic_value = False
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_region_exiting, False
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("region_exiting", {}).get("enabled") == False):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionAlarmInputSwitch(SwitchEntity):
    """Enable/disable alarm input port in camera config (not physical contact state)."""

    _attr_unique_id = "hikvision_alarm_input_1"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Alarm Input 1 Enabled"
        self._attr_unique_id = f"{host}_alarm_input_1"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if alarm input is enabled in camera config."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        if not self.available:
            return None

        if self.coordinator.data and "alarm_input" in self.coordinator.data:
            return self.coordinator.data["alarm_input"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Enable alarm input port."""
        self._optimistic_value = True
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_alarm_input, 1, True
        )

        if success:
            live = await _async_sync_alarm_input_state(
                self.coordinator, self.hass, self.api, 1
            )
            if live is True:
                self._optimistic_value = None
        else:
            self._optimistic_value = None
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable alarm input port."""
        self._optimistic_value = False
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_alarm_input, 1, False
        )

        if success:
            live = await _async_sync_alarm_input_state(
                self.coordinator, self.hass, self.api, 1
            )
            if live is False:
                self._optimistic_value = None
        else:
            self._optimistic_value = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionAlarmOutputSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for alarm output relay (external siren / beeper)."""

    _attr_icon = "mdi:alarm-light-outline"

    def __init__(self, coordinator: HikvisionDataUpdateCoordinator, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str, port_no: int = 1):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.api = api
        self._host = host
        self._entry = entry
        self._port_no = port_no
        self._device_name = device_name
        self._data_key = alarm_output_data_key(device_name, port_no)
        self._attr_unique_id = f"{host}_alarm_output_{port_no}"
        self._attr_name = f"{device_name} Alarm Output {port_no}"
        self._attr_device_info = get_primary_device_info(coordinator.hass, entry)
        self._optimistic_value = None

    @property
    def is_on(self) -> bool | None:
        """Return True when alarm output relay is active."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._data_key, False)

    async def async_turn_on(self, **kwargs):
        """Drive alarm output high."""
        self._optimistic_value = True
        self.async_write_ha_state()
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_alarm_output, self._port_no, True
            )
            if not success:
                raise HomeAssistantError("Failed to set alarm output on")
            live = await _async_sync_alarm_output_state(
                self.coordinator, self.hass, self.api, self._data_key, self._port_no
            )
            if live is True:
                self._optimistic_value = None
        except Exception as err:
            self._optimistic_value = None
            raise HomeAssistantError(f"Failed to set alarm output on: {err}") from err
        finally:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Drive alarm output low."""
        self._optimistic_value = False
        self.async_write_ha_state()
        try:
            success = await self.hass.async_add_executor_job(
                self.api.set_alarm_output, self._port_no, False
            )
            if not success:
                raise HomeAssistantError("Failed to set alarm output off")
            live = await _async_sync_alarm_output_state(
                self.coordinator, self.hass, self.api, self._data_key, self._port_no
            )
            if live is False:
                self._optimistic_value = None
        except Exception as err:
            self._optimistic_value = None
            raise HomeAssistantError(f"Failed to set alarm output off: {err}") from err
        finally:
            self.async_write_ha_state()
