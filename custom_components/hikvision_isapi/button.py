"""Button platform for Hikvision ISAPI."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

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
        HikvisionTestToneButton(api, entry, host, device_name),
        HikvisionTestAudioAlarmButton(api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionRestartButton(ButtonEntity):
    """Button entity for restarting the camera."""

    _attr_unique_id = "hikvision_restart_button"
    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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


class HikvisionTestToneButton(ButtonEntity):
    """Button entity for playing test tone (testing purposes)."""

    _attr_unique_id = "hikvision_test_tone_button"
    _attr_icon = "mdi:music-note"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the button."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Test Tone"
        self._attr_unique_id = f"{host}_test_tone_button"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Test tone button pressed for %s", self._host)
        success = await self.hass.async_add_executor_job(self.api.play_test_tone)
        if success:
            _LOGGER.info("Test tone played successfully")
        else:
            _LOGGER.error("Failed to play test tone")


class HikvisionTestAudioAlarmButton(ButtonEntity):
    """Button entity for testing audio alarm playback."""

    _attr_unique_id = "hikvision_test_audio_alarm_button"
    _attr_icon = "mdi:alarm"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, api: HikvisionISAPI, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the button."""
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Test Audio Alarm"
        self._attr_unique_id = f"{host}_test_audio_alarm_button"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Test audio alarm button pressed for %s", self._host)
        success = await self.hass.async_add_executor_job(self.api.test_audio_alarm)
        if success:
            _LOGGER.info("Audio alarm test triggered successfully")
        else:
            _LOGGER.warning("Failed to trigger audio alarm test - endpoint may not be available")

