"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.device_registry import format_mac

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
    }
)


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
        
        # Show form with pre-filled values
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_USERNAME, default="admin"): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=300)
                    ),
                }
            ),
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        # If coming from DHCP discovery, use discovered host as default
        discovered_host = self.context.get("discovered_host")
        
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
                    errors["base"] = "invalid_auth"
                elif response.status_code == 403:
                    errors["base"] = "invalid_auth"
                elif response.status_code == 404:
                    errors["base"] = "cannot_connect"
                elif not response.ok:
                    errors["base"] = "cannot_connect"
                else:
                    # Connection successful, proceed with setup
                    # Only set unique_id if not already set (e.g., from DHCP discovery)
                    if not self.unique_id:
                        await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=host, data=user_input)
                    
            except requests.exceptions.Timeout:
                errors["base"] = "timeout"
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected error during setup: %s", e)
                errors["base"] = "unknown"

        # Use discovered host as default if available, otherwise use empty schema
        schema = DATA_SCHEMA
        if discovered_host:
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST, default=discovered_host): str,
                    vol.Required(CONF_USERNAME, default="admin"): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=300)
                    ),
                }
            )
        
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry."""
        errors = {}
        entry = self._get_flow_context_entry()
        
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
                    errors["base"] = "invalid_auth"
                elif response.status_code == 403:
                    errors["base"] = "invalid_auth"
                elif response.status_code == 404:
                    errors["base"] = "cannot_connect"
                elif not response.ok:
                    errors["base"] = "cannot_connect"
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
                errors["base"] = "timeout"
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected error during reconfiguration: %s", e)
                errors["base"] = "unknown"

        # Pre-fill form with existing values
        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "admin")): str,
                vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            }
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=reconfigure_schema, errors=errors
        )
