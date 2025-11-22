from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        HikvisionIRModeSensor(coordinator),
    ])


class HikvisionIRModeSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Hikvision IR Mode"
    _attr_unique_id = "hikvision_ir_mode"

    @property
    def state(self):
        root = self.coordinator.data
        mode = root.findtext(".//IrcutFilterType")
        return mode
