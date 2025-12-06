import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.network import async_get_source_ip

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, ALARM_SERVER_PATH, CONF_SET_ALARM_SERVER, CONF_ALARM_SERVER_HOST
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
        
        # Store device info in API instance
        api.device_info = device_info
        
        # Get capabilities and discover cameras
        capabilities = await hass.async_add_executor_job(api.get_capabilities)
        api.capabilities = capabilities
        cameras = await hass.async_add_executor_job(api.get_cameras)
        api.cameras = cameras
        
        _LOGGER.info("Discovered %d camera(s) on %s (NVR: %s)", len(cameras), host, capabilities.get("is_nvr", False))
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
    
    # Store data BEFORE creating coordinator (coordinator needs it)
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "device_info": device_info,
        "capabilities": capabilities,
        "cameras": cameras,
        "host": host,
        **entry.data
    }
    
    # Create coordinator
    coordinator = HikvisionDataUpdateCoordinator(hass, entry, api, update_interval)
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in data
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "select", "number", "media_player", "binary_sensor", "camera", "button", "switch"]
    )

    # Only register notification view once if multiple instances
    if get_first_instance_unique_id(hass) == entry.unique_id:
        hass.http.register_view(EventNotificationsView(hass))

    # Set alarm server if enabled
    if entry.data.get(CONF_SET_ALARM_SERVER, True):
        alarm_server_host = entry.data.get(CONF_ALARM_SERVER_HOST)
        if not alarm_server_host:
            local_ip = await async_get_source_ip(hass)
            alarm_server_host = f"http://{local_ip}:8123"
        try:
            success = await hass.async_add_executor_job(
                api.set_alarm_server, alarm_server_host, ALARM_SERVER_PATH
            )
            if success:
                _LOGGER.info("Successfully configured notification host on camera")
            else:
                _LOGGER.warning("Failed to configure notification host on camera")
        except Exception as e:
            _LOGGER.error("Error configuring notification host: %s", e)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Reset alarm server if it was set
    if entry.data.get(CONF_SET_ALARM_SERVER, True):
        api = hass.data[DOMAIN][entry.entry_id].get("api")
        if api:
            try:
                await hass.async_add_executor_job(
                    api.set_alarm_server, "http://0.0.0.0:80", "/"
                )
            except Exception:
                pass  # Ignore errors on unload
    
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
