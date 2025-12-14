"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries, data_entry_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.device_registry import format_mac
from homeassistant.components.network import async_get_source_ip

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    CONF_SET_ALARM_SERVER,
    CONF_ALARM_SERVER_HOST,
    CONF_VERIFY_SSL,
    RTSP_PORT_FORCED,
)
from .api import _extract_error_message

def get_basic_schema(default_host=None):
    """Get basic schema with required fields only."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=default_host or ""): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("configure_advanced", default=False): bool,
    })

def get_advanced_schema(default_alarm_server=None, set_alarm_server=True):
    """Get advanced options schema."""
    schema = {
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
        vol.Required(CONF_SET_ALARM_SERVER, default=set_alarm_server): bool,
        vol.Optional(RTSP_PORT_FORCED): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    }
    
    # Only show alarm server if set_alarm_server is enabled
    if set_alarm_server:
        schema[vol.Required(CONF_ALARM_SERVER_HOST, default=default_alarm_server or "")] = str
    
    return vol.Schema(schema)


class HikvisionISAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = 1

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> config_entries.ConfigFlowResult:
        """Handle DHCP discovery."""
        _LOGGER.info("DHCP discovery triggered: IP=%s, MAC=%s, Hostname=%s", 
                     discovery_info.ip, discovery_info.macaddress, discovery_info.hostname)
        
        host = discovery_info.ip
        macaddress = discovery_info.macaddress
        
        if not host or not macaddress:
            return self.async_abort(reason="invalid_discovery_info")
        
        # Format MAC address using Home Assistant's helper (normalizes to uppercase without separators)
        mac_address = format_mac(macaddress)
        
        # Use MAC address as unique_id
        await self.async_set_unique_id(mac_address)
        try:
            self._abort_if_unique_id_configured()
        except data_entry_flow.AbortFlow:
            # Device already configured, abort discovery
            return self.async_abort(reason="already_configured")
        
        # Try to get device info for better discovery display
        device_name = discovery_info.hostname or host
        try:
            # Try to get device name from camera (without auth, might fail but worth trying)
            url = f"http://{host}/ISAPI/System/deviceInfo"
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(url, verify=False, timeout=3)
            )
            if response.ok:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                name_elem = root.find(".//{http://www.hikvision.com/ver20/XMLSchema}deviceName")
                if name_elem is not None and name_elem.text:
                    device_name = name_elem.text.strip()
        except Exception:
            pass  # Fallback to hostname or IP
        
        # Store discovered host and device name in context for use in user step
        self.context.update({
            "discovered_host": host,
            "discovered_device_name": device_name,
        })
        
        # Show form with pre-filled values (will use same schema as user step)
        return self.async_show_form(
            step_id="user",
            data_schema=get_basic_schema(host),
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step (basic credentials)."""
        errors = {}
        
        # If coming from DHCP discovery, use discovered host as default
        discovered_host = self.context.get("discovered_host")
        
        if user_input is not None:
            # Validate basic fields
            host = user_input.get(CONF_HOST, "").strip()
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            configure_advanced = user_input.get("configure_advanced", False)
            
            # Basic validation
            if not host:
                errors[CONF_HOST] = "host_required"
            if not username:
                errors[CONF_USERNAME] = "username_required"
            if not password:
                errors[CONF_PASSWORD] = "password_required"
            
            # If basic validation passed, test connection
            if not errors:
                try:
                    # Test connection with device info endpoint
                    url = f"http://{host}/ISAPI/System/deviceInfo"
                    response = await self.hass.async_add_executor_job(
                        lambda: requests.get(
                            url,
                            auth=(username, password),
                            verify=verify_ssl,
                            timeout=10
                        )
                    )
                    
                    # Try to get device name for better discovery title
                    device_name = host
                    try:
                        if response.ok:
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(response.text)
                            name_elem = root.find(".//{http://www.hikvision.com/ver20/XMLSchema}deviceName")
                            if name_elem is not None and name_elem.text:
                                device_name = name_elem.text.strip()
                    except Exception:
                        pass  # Fallback to host if name extraction fails
                    
                    if response.status_code == 401:
                        # Extract camera error message (HTML tags already removed by _extract_error_message)
                        error_msg = _extract_error_message(response)
                        # Use extracted message if it's meaningful (HTML already stripped)
                        if error_msg and error_msg != "OK" and "Invalid Operation" not in error_msg and len(error_msg) > 5:
                            errors["base"] = f"invalid_auth: {error_msg}"
                        else:
                            errors["base"] = "invalid_auth"
                    elif response.status_code == 403:
                        # Extract camera error message (HTML tags already removed by _extract_error_message)
                        error_msg = _extract_error_message(response)
                        # Use extracted message if it's meaningful (HTML already stripped)
                        if error_msg and error_msg != "OK" and "Invalid Operation" not in error_msg and len(error_msg) > 5:
                            errors["base"] = f"invalid_auth: {error_msg}"
                        else:
                            errors["base"] = "invalid_auth"
                    elif response.status_code == 404:
                        errors["base"] = f"cannot_connect: Endpoint not found - camera may not support ISAPI at {host}"
                    elif not response.ok:
                        # Extract camera error message
                        error_msg = _extract_error_message(response)
                        if error_msg and error_msg != "OK":
                            errors["base"] = f"cannot_connect: {error_msg}"
                        else:
                            errors["base"] = f"cannot_connect: HTTP {response.status_code}"
                    else:
                        # Connection successful
                        # Only set unique_id if not already set (e.g., from DHCP discovery)
                        if not self.unique_id:
                            await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()
                        
                        # Store basic data in context for next step or final creation
                        self.context["user_input"] = {
                            CONF_HOST: host,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_VERIFY_SSL: verify_ssl,
                            "device_name": device_name,  # Store for title
                        }
                        
                        # If user wants to configure advanced options, go to advanced step
                        if configure_advanced:
                            return await self.async_step_advanced()
                        
                        # Otherwise, use defaults and create entry
                        local_ip = await async_get_source_ip(self.hass)
                        default_alarm_server = f"http://{local_ip}:8123"
                        
                        entry_data = {
                            **self.context["user_input"],
                            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                            CONF_SET_ALARM_SERVER: True,
                            CONF_ALARM_SERVER_HOST: default_alarm_server,
                        }
                        # Remove device_name from entry_data (only used for title)
                        entry_data.pop("device_name", None)
                        
                        return self.async_create_entry(title=device_name, data=entry_data)
                        
                except requests.exceptions.Timeout:
                    errors["base"] = "timeout: Camera did not respond within 10 seconds - check network connection"
                except requests.exceptions.ConnectionError as e:
                    errors["base"] = f"cannot_connect: Unable to reach camera at {host} - check IP address and network"
                except Exception as e:
                    _LOGGER.exception("Unexpected error during setup: %s", e)
                    errors["base"] = f"unknown: {str(e)}"

        # Show basic form
        return self.async_show_form(
            step_id="user", data_schema=get_basic_schema(discovered_host), errors=errors
        )

    async def async_step_advanced(self, user_input=None):
        """Handle advanced options step."""
        errors = {}
        
        # Get basic data from context
        basic_data = self.context.get("user_input", {})
        if not basic_data:
            return self.async_abort(reason="no_basic_data")
        
        # Get local IP for alarm server default
        local_ip = await async_get_source_ip(self.hass)
        default_alarm_server = f"http://{local_ip}:8123"
        
        if user_input is not None:
            set_alarm_server = user_input.get(CONF_SET_ALARM_SERVER, True)
            
            # If just toggling alarm server checkbox, re-show form
            if CONF_SET_ALARM_SERVER in user_input and not any(k in user_input for k in [CONF_UPDATE_INTERVAL, CONF_ALARM_SERVER_HOST]):
                schema = get_advanced_schema(default_alarm_server, set_alarm_server=set_alarm_server)
                return self.async_show_form(step_id="advanced", data_schema=schema, errors=errors)
            
            # Validate alarm server if enabled
            if set_alarm_server and not user_input.get(CONF_ALARM_SERVER_HOST, "").strip():
                errors[CONF_ALARM_SERVER_HOST] = "alarm_server_required"
            
            if not errors:
                # Merge basic and advanced data
                entry_data = {
                    **basic_data,
                    CONF_UPDATE_INTERVAL: user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    CONF_SET_ALARM_SERVER: set_alarm_server,
                    CONF_ALARM_SERVER_HOST: user_input.get(CONF_ALARM_SERVER_HOST, default_alarm_server) if set_alarm_server else default_alarm_server,
                    RTSP_PORT_FORCED: user_input.get(RTSP_PORT_FORCED),
                }
                # Remove device_name from entry_data (only used for title)
                device_name = entry_data.pop("device_name", basic_data.get(CONF_HOST, "Hikvision"))
                
                return self.async_create_entry(title=device_name, data=entry_data)
            else:
                # If there are errors, show form with errors
                schema = get_advanced_schema(default_alarm_server, set_alarm_server=set_alarm_server)
                return self.async_show_form(step_id="advanced", data_schema=schema, errors=errors)
        
        # Show advanced form (initial load)
        schema = get_advanced_schema(default_alarm_server, set_alarm_server=True)
        return self.async_show_form(
            step_id="advanced", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry."""
        errors = {}
        entry = self._get_reconfigure_entry()
        
        if user_input is not None:
            # Validate credentials by attempting to connect
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            verify_ssl = user_input.get(CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, True))
            
            try:
                # Test connection with device info endpoint
                url = f"http://{host}/ISAPI/System/deviceInfo"
                response = await self.hass.async_add_executor_job(
                    lambda: requests.get(
                        url,
                        auth=(username, password),
                        verify=verify_ssl,
                        timeout=10
                    )
                )
                
                # Try to get device name for better title
                device_name = host
                try:
                    if response.ok:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.text)
                        name_elem = root.find(".//{http://www.hikvision.com/ver20/XMLSchema}deviceName")
                        if name_elem is not None and name_elem.text:
                            device_name = name_elem.text.strip()
                except Exception:
                    pass  # Fallback to host if name extraction fails
                
                if response.status_code == 401:
                    # Extract camera error message (HTML tags already removed by _extract_error_message)
                    error_msg = _extract_error_message(response)
                    # Use extracted message if it's meaningful (HTML already stripped)
                    if error_msg and error_msg != "OK" and len(error_msg) > 5:
                        errors["base"] = f"invalid_auth: {error_msg}"
                    else:
                        errors["base"] = "invalid_auth"
                elif response.status_code == 403:
                    # Extract camera error message (HTML tags already removed by _extract_error_message)
                    error_msg = _extract_error_message(response)
                    # Use extracted message if it's meaningful (HTML already stripped)
                    if error_msg and error_msg != "OK" and len(error_msg) > 5:
                        errors["base"] = f"invalid_auth: {error_msg}"
                    else:
                        errors["base"] = "invalid_auth"
                elif response.status_code == 404:
                    errors["base"] = f"cannot_connect: Endpoint not found - camera may not support ISAPI at {user_input[CONF_HOST]}"
                elif not response.ok:
                    # Extract camera error message
                    error_msg = _extract_error_message(response)
                    if error_msg and error_msg != "OK":
                        errors["base"] = f"cannot_connect: {error_msg}"
                    else:
                        errors["base"] = f"cannot_connect: HTTP {response.status_code}"
                else:
                    # Connection successful, update entry
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, **user_input},
                        title=device_name,
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
                    
            except requests.exceptions.Timeout:
                errors["base"] = "timeout: Camera did not respond within 10 seconds - check network connection"
            except requests.exceptions.ConnectionError as e:
                errors["base"] = f"cannot_connect: Unable to reach camera at {user_input[CONF_HOST]} - check IP address and network"
            except Exception as e:
                _LOGGER.exception("Unexpected error during reconfiguration: %s", e)
                errors["base"] = f"unknown: {str(e)}"

        # Get local IP for alarm server default
        local_ip = await async_get_source_ip(self.hass)
        default_alarm_server = entry.data.get(CONF_ALARM_SERVER_HOST, f"http://{local_ip}:8123")
        
        # Pre-fill form with existing values (always show advanced for reconfigure)
        existing_set_alarm = entry.data.get(CONF_SET_ALARM_SERVER, True)
        existing_update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        
        reconfigure_schema = vol.Schema({
            vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
            vol.Optional(CONF_VERIFY_SSL, default=entry.data.get(CONF_VERIFY_SSL, True)): bool,
            vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "admin")): str,
            vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=existing_update_interval
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            vol.Required(
                CONF_SET_ALARM_SERVER,
                default=existing_set_alarm
            ): bool,
        })
        
        # Only include alarm server if enabled
        if existing_set_alarm:
            reconfigure_schema = reconfigure_schema.extend({
                vol.Required(
                    CONF_ALARM_SERVER_HOST,
                    default=default_alarm_server
                ): str,
            })
        
        # Add RTSP port forced option
        reconfigure_schema = reconfigure_schema.extend({
            vol.Optional(
                RTSP_PORT_FORCED,
                default=entry.data.get(RTSP_PORT_FORCED)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        })

        return self.async_show_form(
            step_id="reconfigure", data_schema=reconfigure_schema, errors=errors
        )
