"""Data update coordinator for Hikvision ISAPI."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HikvisionISAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HikvisionDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hikvision ISAPI data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HikvisionISAPI,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data['host']}",
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Hikvision ISAPI."""
        try:
            # Fetch all camera state data
            ircut_data = await self.hass.async_add_executor_job(
                self.api.get_ircut_filter
            )
            light_mode = await self.hass.async_add_executor_job(
                self.api.get_supplement_light
            )

            return {
                "ircut": ircut_data,
                "light_mode": light_mode,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

