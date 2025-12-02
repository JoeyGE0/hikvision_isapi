"""Switch platform for Hikvision ISAPI."""
from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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

    entities = [
        HikvisionNoiseReduceSwitch(coordinator, api, entry, host, device_name),
        HikvisionMotionDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionTamperDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionIntrusionDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionLineCrossingDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionSceneChangeDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionRegionEntranceDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionRegionExitingDetectionSwitch(coordinator, api, entry, host, device_name),
    ]

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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if noise reduction is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
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
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if self.coordinator.data and "motion" in self.coordinator.data:
            return self.coordinator.data["motion"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on motion detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
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
        if self._optimistic_value is not None:
            return self._optimistic_value
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if intrusion detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if self.coordinator.data and "field_detection" in self.coordinator.data:
            return self.coordinator.data["field_detection"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on intrusion detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if line crossing detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if self.coordinator.data and "line_detection" in self.coordinator.data:
            return self.coordinator.data["line_detection"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on line crossing detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if scene change detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if self.coordinator.data and "scene_change" in self.coordinator.data:
            return self.coordinator.data["scene_change"].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on scene change detection."""
        self._optimistic_value = True
        self.async_write_ha_state()
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if region entrance detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return if region exiting detection is enabled."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
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
