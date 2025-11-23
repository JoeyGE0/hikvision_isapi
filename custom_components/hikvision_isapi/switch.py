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
