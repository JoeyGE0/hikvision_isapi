import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, ALARM_SERVER_PATH
from .api import HikvisionISAPI, AuthenticationError
from .coordinator import HikvisionDataUpdateCoordinator
from .notifications import EventNotificationsView

_LOGGER = logging.getLogger(__name__)


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
    
    # Fetch device info - validate connection and credentials
    try:
        device_info = await hass.async_add_executor_job(api.get_device_info)
        if not device_info:
            raise ConfigEntryNotReady(
                f"Failed to connect to {host}. Please check your credentials and network connection."
            )
    except AuthenticationError as err:
        _LOGGER.error("Authentication failed for %s: %s", host, err)
        raise ConfigEntryNotReady(
            f"Authentication failed for {host}. Please check your username and password. "
            f"Note: Username is case-sensitive (e.g., 'admin' not 'Admin')."
        ) from err
    except Exception as err:
        _LOGGER.error("Failed to connect to %s: %s", host, err)
        raise ConfigEntryNotReady(
            f"Failed to connect to {host}: {err}. Please check your network connection and that the device is online."
        ) from err
    
    device_registry = dr.async_get(hass)
    
    # Build identifiers - use MAC address if available for auto-linking
    identifiers = {(DOMAIN, host)}
    if mac_address := device_info.get("macAddress"):
        # Add MAC address identifier for auto-linking with other integrations (UniFi, etc.)
        identifiers.add(("mac", mac_address.lower()))
    
    # Add serial number as additional identifier if available
    if serial_number := device_info.get("serialNumber"):
        identifiers.add((DOMAIN, serial_number))
    
    # Build connections - MAC address for display in device info
    connections = set()
    if mac_address := device_info.get("macAddress"):
        connections.add((dr.CONNECTION_NETWORK_MAC, mac_address.lower()))
    
    # Only include hardware version if it's meaningful (not "0x0" or empty)
    hw_version = device_info.get("hardwareVersion")
    if hw_version in ("0x0", "0", "", None):
        hw_version = None
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=identifiers,
        connections=connections,
        manufacturer=device_info.get("manufacturer", "Hikvision").title(),
        model=device_info.get("model", "Hikvision Camera"),
        name=device_info.get("deviceName", host),
        sw_version=device_info.get("firmwareVersion"),
        hw_version=hw_version,
    )
    
    # Create coordinator
    coordinator = HikvisionDataUpdateCoordinator(hass, entry, api, update_interval)
    await coordinator.async_config_entry_first_refresh()
    
    # Register webhook endpoint for event notifications (only once per integration instance)
    if get_first_instance_unique_id(hass) == entry.unique_id:
        hass.http.register_view(EventNotificationsView(hass))
        _LOGGER.info("Registered webhook endpoint: %s", ALARM_SERVER_PATH)
    
    # Store coordinator, API and device info
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "device_info": device_info,
        "host": host,
        **entry.data
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "select", "number", "media_player", "binary_sensor", "camera", "button", "switch"]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "select", "number", "media_player", "binary_sensor", "camera", "button", "switch"]
    )
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def get_first_instance_unique_id(hass: HomeAssistant) -> str:
    """Get entry unique_id for first instance of integration."""
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN) if not entry.disabled_by]
    if entries:
        return entries[0].unique_id
    return ""
