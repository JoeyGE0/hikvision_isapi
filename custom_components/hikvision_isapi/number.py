"""Number platform for Hikvision ISAPI."""
import logging
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN
from .api import HikvisionISAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up number entities for the entry."""
    config = hass.data[DOMAIN][entry.entry_id]

    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    api = HikvisionISAPI(host, username, password)

    entities = [
        HikvisionIRSensitivityNumber(api, host),
        HikvisionIRFilterTimeNumber(api, host),
    ]

    async_add_entities(entities, True)


class HikvisionIRSensitivityNumber(NumberEntity):
    """Number entity for IR sensitivity."""

    _attr_name = "IR Sensitivity"
    _attr_unique_id = "hikvision_ir_sensitivity"
    _attr_native_min_value = 0
    _attr_native_max_value = 7
    _attr_native_step = 1
    _attr_icon = "mdi:adjust"

    def __init__(self, api: HikvisionISAPI, host: str):
        """Initialize the number entity."""
        self.api = api
        self._host = host
        self._attr_unique_id = f"{host}_ir_sensitivity"
        self._attr_native_value = None

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._attr_native_value

    def update(self):
        """Fetch current IR sensitivity from camera."""
        ircut_data = self.api.get_ircut_filter()
        sensitivity = ircut_data.get("sensitivity")
        if sensitivity is not None:
            self._attr_native_value = float(sensitivity)

    async def async_set_native_value(self, value: float):
        """Set the value."""
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_sensitivity, int(value)
        )
        if success:
            self._attr_native_value = value
            self.async_write_ha_state()


class HikvisionIRFilterTimeNumber(NumberEntity):
    """Number entity for IR filter time."""

    _attr_name = "IR Filter Time"
    _attr_unique_id = "hikvision_ir_filter_time"
    _attr_native_min_value = 5
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(self, api: HikvisionISAPI, host: str):
        """Initialize the number entity."""
        self.api = api
        self._host = host
        self._attr_unique_id = f"{host}_ir_filter_time"
        self._attr_native_value = None

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._attr_native_value

    def update(self):
        """Fetch current IR filter time from camera."""
        ircut_data = self.api.get_ircut_filter()
        filter_time = ircut_data.get("filter_time")
        if filter_time is not None:
            self._attr_native_value = float(filter_time)

    async def async_set_native_value(self, value: float):
        """Set the value."""
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_filter_time, int(value)
        )
        if success:
            self._attr_native_value = value
            self.async_write_ha_state()

