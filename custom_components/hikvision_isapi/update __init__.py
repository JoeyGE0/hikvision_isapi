import asyncio
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    host = entry.data["host"]
    user = entry.data["username"]
    pwd = entry.data["password"]

    async def async_update_data():
        try:
            url = f"http://{host}/ISAPI/Image/channels/1/IrcutFilter"
            response = await hass.async_add_executor_job(
                requests.get,
                url,
                {"auth": (user, pwd), "verify": False}
            )
            if response.status_code != 200:
                raise UpdateFailed(f"HTTP {response.status_code}")

            return ET.fromstring(response.text)

        except Exception as err:
            raise UpdateFailed(f"Error: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="hikvision_isapi",
        update_method=async_update_data,
        update_interval=timedelta(seconds=3),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, ["sensor"])
    return True
