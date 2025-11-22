"""Button platform for Hikvision ISAPI."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import HikvisionISAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up button entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionRestartButton(api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionRestartButton(ButtonEntity):
    """Button entity for restarting the camera."""

    _attr_unique_id = "hikvision_restart_button"
    _attr_icon = "mdi:restart"

    def __init__(self, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the button."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Restart"
        self._attr_unique_id = f"{host}_restart_button"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Restart button pressed for %s", self._host)
        success = await self.hass.async_add_executor_job(self.api.restart)
        if success:
            _LOGGER.info("Camera restart command sent successfully")
        else:
            _LOGGER.error("Failed to send restart command")

