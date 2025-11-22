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
    api = data["api"]
    host = data["host"]

    entities = [
        HikvisionLightModeSelect(api, entry, host),
        HikvisionIRModeSelect(api, entry, host),
    ]

    async_add_entities(entities, True)


class HikvisionLightModeSelect(SelectEntity):
    """Select entity for supplement light mode."""

    _attr_name = "Light Mode"
    _attr_unique_id = "hikvision_light_mode"
    _attr_options = ["eventIntelligence", "irLight", "close"]
    _attr_icon = "mdi:lightbulb"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the select entity."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_light_mode"
        self._current_option = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current_option

    def update(self):
        """Fetch current light mode from camera."""
        mode = self.api.get_supplement_light()
        if mode:
            # Map API values to our options
            if mode == "eventIntelligence":
                self._current_option = "eventIntelligence"
            elif mode == "irLight":
                self._current_option = "irLight"
            elif mode == "close":
                self._current_option = "close"
            else:
                self._current_option = mode

    async def async_select_option(self, option: str):
        """Change the selected option."""
        success = await self.hass.async_add_executor_job(
            self.api.set_supplement_light, option
        )
        if success:
            self._current_option = option
            self.async_write_ha_state()


class HikvisionIRModeSelect(SelectEntity):
    """Select entity for IR cut mode."""

    _attr_name = "IR Mode"
    _attr_unique_id = "hikvision_ir_mode"
    _attr_options = ["auto", "day", "night"]
    _attr_icon = "mdi:weather-night"

    def __init__(self, api, entry: ConfigEntry, host: str):
        """Initialize the select entity."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_unique_id = f"{host}_ir_mode"
        self._current_option = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current_option

    def update(self):
        """Fetch current IR mode from camera."""
        ircut_data = self.api.get_ircut_filter()
        mode = ircut_data.get("mode")
        if mode:
            self._current_option = mode

    async def async_select_option(self, option: str):
        """Change the selected option."""
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_mode, option
        )
        if success:
            self._current_option = option
            self.async_write_ha_state()

