"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries
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
)
from .api import _extract_error_message

def get_data_schema(default_host=None, default_alarm_server=None, set_alarm_server=True):
    """Get data schema with defaults and human-readable labels."""
    # Update interval options (dropdown-friendly values)
    update_interval_options = [5, 10, 15, 30, 60, 120, 300]
    
    # Basic required fields
    schema = {
        vol.Required(CONF_HOST, default=default_host or ""): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.In(update_interval_options),
        vol.Required(CONF_SET_ALARM_SERVER, default=set_alarm_server): bool,
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
        self._abort_if_unique_id_configured()
        
        # Store discovered host in context for use in user step
        self.context.update({"discovered_host": host})
        
        # Show form with pre-filled values (will use same schema as user step)
        # Get local IP for alarm server default
        try:
            local_ip = await async_get_source_ip(self.hass)
            default_alarm_server = f"http://{local_ip}:8123"
        except Exception:
            default_alarm_server = None
        
        return self.async_show_form(
            step_id="user",
            data_schema=get_data_schema(host, default_alarm_server),
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        set_alarm_server = True
        
        # If coming from DHCP discovery, use discovered host as default
        discovered_host = self.context.get("discovered_host")
        
        # Get local IP for alarm server default
        local_ip = await async_get_source_ip(self.hass)
        default_alarm_server = f"http://{local_ip}:8123"
        
        if user_input is not None:
            set_alarm_server = user_input.get(CONF_SET_ALARM_SERVER, True)
            
            # If just toggling alarm server checkbox, re-show form
            if CONF_SET_ALARM_SERVER in user_input and not any(k in user_input for k in [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]):
                schema = get_data_schema(discovered_host, default_alarm_server, set_alarm_server=set_alarm_server)
                return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
            
            # Validate credentials by attempting to connect
            host = user_input.get(CONF_HOST, "").strip()
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            
            # Basic validation
            if not host:
                errors[CONF_HOST] = "host_required"
            if not username:
                errors[CONF_USERNAME] = "username_required"
            if not password:
                errors[CONF_PASSWORD] = "password_required"
            
            # Validate alarm server if enabled
            if set_alarm_server and not user_input.get(CONF_ALARM_SERVER_HOST, "").strip():
                errors[CONF_ALARM_SERVER_HOST] = "alarm_server_required"
            
            # If basic validation passed, test connection
            if not errors:
                try:
                    # Test connection with device info endpoint
                    url = f"http://{host}/ISAPI/System/deviceInfo"
                    response = await self.hass.async_add_executor_job(
                        lambda: requests.get(
                            url,
                            auth=(username, password),
                            verify=False,
                            timeout=10
                        )
                    )
                    
                    if response.status_code == 401:
                        # Extract camera error message
                        error_msg = _extract_error_message(response)
                        if error_msg and error_msg != "OK" and "Invalid Operation" not in error_msg:
                            errors["base"] = f"invalid_auth: {error_msg}"
                        else:
                            errors["base"] = "invalid_auth"
                    elif response.status_code == 403:
                        # Extract camera error message
                        error_msg = _extract_error_message(response)
                        if error_msg and error_msg != "OK" and "Invalid Operation" not in error_msg:
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
                        # Connection successful, proceed with setup
                        # Only set unique_id if not already set (e.g., from DHCP discovery)
                        if not self.unique_id:
                            await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()
                        
                        # Set defaults for optional fields if not provided
                        if CONF_UPDATE_INTERVAL not in user_input:
                            user_input[CONF_UPDATE_INTERVAL] = DEFAULT_UPDATE_INTERVAL
                        if CONF_SET_ALARM_SERVER not in user_input:
                            user_input[CONF_SET_ALARM_SERVER] = True
                        if CONF_ALARM_SERVER_HOST not in user_input or not user_input[CONF_ALARM_SERVER_HOST]:
                            user_input[CONF_ALARM_SERVER_HOST] = default_alarm_server
                        
                        return self.async_create_entry(title=host, data=user_input)
                        
                except requests.exceptions.Timeout:
                    errors["base"] = "timeout: Camera did not respond within 10 seconds - check network connection"
                except requests.exceptions.ConnectionError as e:
                    errors["base"] = f"cannot_connect: Unable to reach camera at {host} - check IP address and network"
                except Exception as e:
                    _LOGGER.exception("Unexpected error during setup: %s", e)
                    errors["base"] = f"unknown: {str(e)}"

        # Use discovered host as default if available
        schema = get_data_schema(discovered_host, default_alarm_server, set_alarm_server=set_alarm_server)
        
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
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
            
            try:
                # Test connection with device info endpoint
                url = f"http://{host}/ISAPI/System/deviceInfo"
                response = await self.hass.async_add_executor_job(
                    lambda: requests.get(
                        url,
                        auth=(username, password),
                        verify=False,
                        timeout=10
                    )
                )
                
                if response.status_code == 401:
                    # Extract camera error message
                    error_msg = _extract_error_message(response)
                    if error_msg and error_msg != "OK":
                        errors["base"] = f"invalid_auth: {error_msg}"
                    else:
                        errors["base"] = "invalid_auth"
                elif response.status_code == 403:
                    # Extract camera error message
                    error_msg = _extract_error_message(response)
                    if error_msg and error_msg != "OK":
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
                        title=host,
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
        
        # Pre-fill form with existing values
        existing_set_alarm = entry.data.get(CONF_SET_ALARM_SERVER, True)
        update_interval_options = [5, 10, 15, 30, 60, 120, 300]
        existing_update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        if existing_update_interval not in update_interval_options:
            # Find closest option
            existing_update_interval = min(update_interval_options, key=lambda x: abs(x - existing_update_interval))
        
        reconfigure_schema = vol.Schema({
            vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "admin")): str,
            vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=existing_update_interval
            ): vol.In(update_interval_options),
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

        return self.async_show_form(
            step_id="reconfigure", data_schema=reconfigure_schema, errors=errors
        )
