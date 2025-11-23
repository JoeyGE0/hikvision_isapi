"""Select platform for Hikvision ISAPI."""
import logging
from homeassistant.components.select import SelectEntity
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
    """Set up select entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionLightModeSelect(coordinator, api, entry, host, device_name),
        HikvisionIRModeSelect(coordinator, api, entry, host, device_name),
        HikvisionMotionTargetTypeSelect(coordinator, api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionLightModeSelect(SelectEntity):
    """Select entity for supplement light mode."""

    _attr_unique_id = "hikvision_light_mode"
    _attr_options = ["Smart", "IR Supplement Light", "Off"]
    _attr_icon = "mdi:lightbulb"
    
    # Map display names to API values
    _api_value_map = {
        "Smart": "eventIntelligence",
        "IR Supplement Light": "irLight",
        "Off": "close"
    }
    # Reverse map for reading
    _display_value_map = {v: k for k, v in _api_value_map.items()}

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Supplement Light"
        self._attr_unique_id = f"{host}_light_mode"
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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data - convert API value to display name
        if self.coordinator.data and "supplement_light" in self.coordinator.data:
            api_value = self.coordinator.data["supplement_light"].get("mode")
            display_value = self._display_value_map.get(api_value)
            if display_value in self._attr_options:
                return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        # Convert display name to API value
        api_value = self._api_value_map.get(option, option)
        
        # Optimistic update - show immediately
        self._optimistic_value = option
        self.async_write_ha_state()
        
        # Send to device (using API value)
        success = await self.hass.async_add_executor_job(
            self.api.set_supplement_light, api_value
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("supplement_light", {}).get("mode") == api_value):
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


class HikvisionIRModeSelect(SelectEntity):
    """Select entity for IR cut mode."""

    _attr_unique_id = "hikvision_ir_mode"
    _attr_options = ["Day", "Night", "Auto"]
    _attr_icon = "mdi:weather-night"
    
    # Map display names to API values
    _api_value_map = {
        "Day": "day",
        "Night": "night",
        "Auto": "auto"
    }
    # Reverse map for reading
    _display_value_map = {v: k for k, v in _api_value_map.items()}

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Day/Night Switch"
        self._attr_unique_id = f"{host}_ir_mode"
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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data - convert API value to display name
        if self.coordinator.data and "ircut" in self.coordinator.data:
            api_value = self.coordinator.data["ircut"].get("mode")
            display_value = self._display_value_map.get(api_value)
            if display_value in self._attr_options:
                return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        # Convert display name to API value
        api_value = self._api_value_map.get(option, option)
        
        # Optimistic update - show immediately
        self._optimistic_value = option
        self.async_write_ha_state()
        
        # Send to device (using API value)
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_mode, api_value
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("ircut", {}).get("mode") == api_value):
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


class HikvisionMotionTargetTypeSelect(SelectEntity):
    """Select entity for motion detection target type."""

    _attr_unique_id = "hikvision_motion_target_type"
    _attr_options = ["human", "vehicle", "human,vehicle"]
    _attr_icon = "mdi:target"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Motion Target Type"
        self._attr_unique_id = f"{host}_motion_target_type"
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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        if self.coordinator.data and "motion" in self.coordinator.data:
            target_type = self.coordinator.data["motion"].get("targetType")
            if target_type and target_type in self._attr_options:
                return target_type
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        self._optimistic_value = option
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_motion_target_type, option
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("motion", {}).get("targetType") == option):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

