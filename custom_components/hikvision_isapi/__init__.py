from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    
    # Get device info and create device
    host = entry.data["host"]
    username = entry.data["username"]
    password = entry.data["password"]
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    
    api = HikvisionISAPI(host, username, password)
    
    # Fetch device info
    device_info = await hass.async_add_executor_job(api.get_device_info)
    
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, host)},
        manufacturer="Hikvision",
        model=device_info.get("model", "Hikvision Camera"),
        name=device_info.get("deviceName", host),
        sw_version=device_info.get("firmwareVersion"),
        hw_version=device_info.get("hardwareVersion"),
    )
    
    # Create coordinator
    coordinator = HikvisionDataUpdateCoordinator(hass, entry, api, update_interval)
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator, API and device info
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "device_info": device_info,
        "host": host,
        **entry.data
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "select", "number"]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "select", "number"]
    )
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
