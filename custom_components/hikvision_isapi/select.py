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

    entities = [
        HikvisionLightModeSelect(coordinator, api, entry, host),
        HikvisionIRModeSelect(coordinator, api, entry, host),
    ]

    async_add_entities(entities)


class HikvisionLightModeSelect(SelectEntity):
    """Select entity for supplement light mode."""

    _attr_name = "Light Mode"
    _attr_unique_id = "hikvision_light_mode"
    _attr_options = ["eventIntelligence", "irLight", "close"]
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_light_mode"

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
        if self.coordinator.data and "light_mode" in self.coordinator.data:
            mode = self.coordinator.data["light_mode"]
            if mode in self._attr_options:
                return mode
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        success = await self.hass.async_add_executor_job(
            self.api.set_supplement_light, option
        )
        if success:
            # Refresh coordinator to get updated state
            await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIRModeSelect(SelectEntity):
    """Select entity for IR cut mode."""

    _attr_name = "IR Mode"
    _attr_unique_id = "hikvision_ir_mode"
    _attr_options = ["auto", "day", "night"]
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_ir_mode"

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
        if self.coordinator.data and "ircut" in self.coordinator.data:
            mode = self.coordinator.data["ircut"].get("mode")
            if mode in self._attr_options:
                return mode
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_mode, option
        )
        if success:
            # Refresh coordinator to get updated state
            await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

