"""Data update coordinator for Hikvision ISAPI."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HikvisionISAPI, AuthenticationError
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
            supplement_light = await self.hass.async_add_executor_job(
                self.api.get_supplement_light
            )
            audio_data = await self.hass.async_add_executor_job(
                self.api.get_two_way_audio
            )
            motion_data = await self.hass.async_add_executor_job(
                self.api.get_motion_detection
            )
            tamper_data = await self.hass.async_add_executor_job(
                self.api.get_tamper_detection
            )
            field_detection = await self.hass.async_add_executor_job(
                self.api.get_field_detection
            )
            line_detection = await self.hass.async_add_executor_job(
                self.api.get_line_detection
            )
            scene_change = await self.hass.async_add_executor_job(
                self.api.get_scene_change_detection
            )
            region_entrance = await self.hass.async_add_executor_job(
                self.api.get_region_entrance
            )
            region_exiting = await self.hass.async_add_executor_job(
                self.api.get_region_exiting
            )
            white_light_time = await self.hass.async_add_executor_job(
                self.api.get_white_light_time
            )
            system_status = await self.hass.async_add_executor_job(
                self.api.get_system_status
            )
            streaming_status = await self.hass.async_add_executor_job(
                self.api.get_streaming_status
            )
            alarm_input = await self.hass.async_add_executor_job(
                self.api.get_alarm_input, 1
            )
            alarm_server = await self.hass.async_add_executor_job(
                self.api.get_alarm_server
            )
            from homeassistant.components.switch import ENTITY_ID_FORMAT
            from homeassistant.util import slugify
            
            data = {
                "ircut": ircut_data,
                "supplement_light": supplement_light,
                "audio": audio_data,
                "motion": motion_data,
                "tamper": tamper_data,
                "field_detection": field_detection,
                "line_detection": line_detection,
                "scene_change": scene_change,
                "region_entrance": region_entrance,
                "region_exiting": region_exiting,
                "white_light_time": white_light_time,
                "system_status": system_status,
                "streaming_status": streaming_status,
                "alarm_input": alarm_input,
                "alarm_server": alarm_server,
            }
            
            # Store alarm output status using unique_id as key
            alarm_output = await self.hass.async_add_executor_job(
                self.api.get_alarm_output, 1
            )
            # Get device name from stored data (with fallback if not available yet)
            from .const import DOMAIN
            device_info = {}
            if DOMAIN in self.hass.data and self.entry.entry_id in self.hass.data[DOMAIN]:
                device_info = self.hass.data[DOMAIN][self.entry.entry_id].get("device_info", {})
            device_name = device_info.get("deviceName", self.entry.data.get("host", ""))
            _id = ENTITY_ID_FORMAT.format(f"{slugify(device_name.lower())}_1_alarm_output")
            data[_id] = alarm_output.get("enabled", False)
            
            return data
        except AuthenticationError as err:
            raise UpdateFailed(
                f"Authentication failed. Please check your username and password in the integration settings. "
                f"Note: Username is case-sensitive (e.g., 'admin' not 'Admin'). Error: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

