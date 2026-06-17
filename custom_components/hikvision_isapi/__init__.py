import logging

import requests
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.components.network import async_get_source_ip

from pathlib import Path

from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, ALARM_SERVER_PATH, CONF_SET_ALARM_SERVER, CONF_ALARM_SERVER_HOST, CONF_VERIFY_SSL, RTSP_PORT_FORCED
from .api import HikvisionISAPI, AuthenticationError
from .coordinator import HikvisionDataUpdateCoordinator
from .device_helpers import build_configuration_url, build_primary_device_info
from .notifications import EventNotificationsView

_LOGGER = logging.getLogger(__name__)

_INTEGRATION_DIR = Path(__file__).resolve().parent

_BASE_PLATFORMS = [
    "sensor",
    "select",
    "number",
    "media_player",
    "binary_sensor",
    "camera",
    "button",
    "switch",
    "siren",
]


def _entry_platforms() -> list[str]:
    """Platforms to load; skip update if update.py missing (partial HACS install)."""
    platforms = list(_BASE_PLATFORMS)
    if (_INTEGRATION_DIR / "update.py").is_file():
        platforms.append("update")
    else:
        _LOGGER.warning(
            "update.py is missing from %s — firmware update entity disabled. "
            "Re-download the integration in HACS (Redownload) to restore it.",
            _INTEGRATION_DIR,
        )
    return platforms


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.info("=== HIKVISION ISAPI: Setting up integration for %s ===", entry.data.get("host", "unknown"))
    hass.data.setdefault(DOMAIN, {})
    
    # Get device info and create device
    host = entry.data["host"]
    username = entry.data["username"]
    password = entry.data["password"]
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    rtsp_port_forced = entry.data.get(RTSP_PORT_FORCED)
    
    api = HikvisionISAPI(host, username, password, verify_ssl=verify_ssl, rtsp_port_forced=rtsp_port_forced)
    
    # Fetch device info - validate connection and credentials
    try:
        device_info = await hass.async_add_executor_job(api.get_device_info)
        if not device_info:
            raise ConfigEntryNotReady(
                f"Connected to {host} but received no device information. "
                f"Confirm ISAPI is enabled on the camera and try again."
            )
        
        # Store device info in API instance
        api.device_info = device_info
        
        # Get capabilities and discover cameras
        capabilities = await hass.async_add_executor_job(api.get_capabilities)
        api.capabilities = capabilities
        cameras = await hass.async_add_executor_job(api.get_cameras)
        api.cameras = cameras
        
        # Detect supported features from capabilities
        try:
            detected_features = await hass.async_add_executor_job(api.detect_features)
            api.detected_features = detected_features
            if not detected_features:
                _LOGGER.warning("Feature detection returned empty - no features detected. This may indicate a problem with capabilities parsing.")
        except Exception as e:
            _LOGGER.error("Feature detection failed: %s. No entities will be added until this is fixed.", e)
            # Return empty dict - don't enable everything, let user know something is wrong
            detected_features = {}
            api.detected_features = detected_features
        
        # Get supported events from Event/triggers API (optional - fallback to empty list if fails)
        supported_events = []
        if hasattr(api, 'get_supported_events'):
            try:
                supported_events = await hass.async_add_executor_job(api.get_supported_events)
                api.supported_events = supported_events
            except Exception as e:
                _LOGGER.warning("Failed to get supported events (will use fallback): %s", e)
                supported_events = []
        else:
            _LOGGER.warning("get_supported_events method not found, using fallback")
        
        _LOGGER.info("Discovered %d camera(s) on %s (NVR: %s), %d supported events", 
                    len(cameras), host, capabilities.get("is_nvr", False), len(supported_events))
    except AuthenticationError as err:
        _LOGGER.error("Authentication failed for %s: %s", host, err)
        raise ConfigEntryAuthFailed(
            f"Authentication failed for {host}. Open the integration and use "
            f"Re-authenticate to enter the password set on the camera after reset "
            f"(username is case-sensitive, e.g. 'admin' not 'Admin')."
        ) from err
    except requests.exceptions.SSLError as err:
        _LOGGER.error("SSL verification failed for %s: %s", host, err)
        raise ConfigEntryNotReady(
            f"SSL verification failed for {host}. Reconfigure the integration and "
            f"disable 'Verify SSL certificate' if the camera uses HTTP."
        ) from err
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as err:
        _LOGGER.error("Cannot reach %s: %s", host, err)
        raise ConfigEntryNotReady(
            f"Cannot reach {host}. Check the camera is online, on the same network, "
            f"and ISAPI is enabled (camera may still be booting after restore)."
        ) from err
    except Exception as err:
        _LOGGER.error("Failed to set up %s: %s", host, err)
        raise ConfigEntryNotReady(
            f"Failed to set up {host}: {err}"
        ) from err
    
    device_registry = dr.async_get(hass)
    
    # Build identifiers - use serial number as primary, fallback to host
    serial_number = device_info.get("serialNumber")
    if serial_number:
        identifiers = {(DOMAIN, serial_number)}
        nvr_device_identifier = serial_number  # For via_device on NVR cameras
    else:
        identifiers = {(DOMAIN, host)}
        nvr_device_identifier = host  # For via_device on NVR cameras
    
    if mac_address := device_info.get("macAddress"):
        # Add MAC address identifier for registry linking with other local integrations
        identifiers.add(("mac", mac_address.lower()))
    
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
        configuration_url=build_configuration_url(host),
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
        "supported_events": supported_events,
        "detected_features": detected_features,
        "host": host,
        "nvr_device_identifier": nvr_device_identifier,  # For via_device on NVR cameras
        "ha_device_info": build_primary_device_info(DOMAIN, device_info, host),
        **entry.data
    }
    
    # Create coordinator
    coordinator = HikvisionDataUpdateCoordinator(hass, entry, api, update_interval)
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in data
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _entry_platforms())

    # Only register notification view once if multiple instances
    if get_first_instance_unique_id(hass) == entry.unique_id:
        view = EventNotificationsView(hass)
        hass.http.register_view(view)
        _LOGGER.info("=== HIKVISION ISAPI: Registered notification webhook at: %s ===", view.url)
    else:
        _LOGGER.info("=== HIKVISION ISAPI: Using existing webhook (not first instance) ===")

    # Set alarm server if enabled
    if entry.data.get(CONF_SET_ALARM_SERVER, True):
        alarm_server_host = entry.data.get(CONF_ALARM_SERVER_HOST)
        if not alarm_server_host:
            local_ip = await async_get_source_ip(hass)
            alarm_server_host = f"http://{local_ip}:8123"
        try:
            actual_path = await hass.async_add_executor_job(
                api.set_alarm_server, alarm_server_host, ALARM_SERVER_PATH
            )
            if actual_path:
                _LOGGER.info("=== HIKVISION ISAPI: Successfully configured notification host on camera (path: %s) ===", actual_path)
                # Update ALARM_SERVER_PATH if it was changed to match existing (e.g., /api/hikvision)
                if actual_path != ALARM_SERVER_PATH:
                    _LOGGER.info("=== HIKVISION ISAPI: Using existing notification path: %s ===", actual_path)
                try:
                    await hass.async_add_executor_job(
                        api.ensure_http_alarm_notifications_for_events,
                        None,
                    )
                except Exception as notify_err:
                    _LOGGER.warning(
                        "=== HIKVISION ISAPI: Could not enable Surveillance Center on event triggers: %s ===",
                        notify_err,
                    )
            else:
                _LOGGER.warning("=== HIKVISION ISAPI: Failed to configure notification host on camera ===")
        except Exception as e:
            _LOGGER.error("=== HIKVISION ISAPI: Error configuring notification host: %s ===", e)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Don't reset alarm server on unload - leave it configured
    # This prevents the camera from being reset to "/" which breaks notifications
    
    await hass.config_entries.async_unload_platforms(entry, _entry_platforms())
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def get_first_instance_unique_id(hass: HomeAssistant) -> str:
    """Get entry unique_id for first instance of integration."""
    entries = [entry for entry in hass.config_entries.async_entries(DOMAIN) if not entry.disabled_by]
    if entries:
        return entries[0].unique_id
    return ""
