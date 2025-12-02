"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    HIKVISION_MAC_PREFIXES,
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
        _LOGGER.info("DHCP discovery triggered for Hikvision ISAPI: IP=%s, MAC=%s, Hostname=%s", 
                     discovery_info.ip, discovery_info.macaddress, discovery_info.hostname)
        
        # Get IP address - use ip attribute directly (DhcpServiceInfo always has ip)
        host = discovery_info.ip
        macaddress = discovery_info.macaddress
        
        if not host:
            _LOGGER.warning("DHCP discovery: No IP address found in discovery_info")
            return self.async_abort(reason="no_ip_address")
        
        if not macaddress:
            _LOGGER.warning("DHCP discovery: No MAC address found in discovery_info")
            return self.async_abort(reason="no_mac_address")
        
        _LOGGER.debug("DHCP discovery: IP=%s, MAC=%s", host, macaddress)
        
        # Normalize MAC address (remove colons/dashes, convert to uppercase)
        mac_normalized = macaddress.replace(":", "").replace("-", "").upper()
        
        # Extract first 6 characters (OUI prefix) and format as XX:XX:XX
        if len(mac_normalized) < 6:
            _LOGGER.warning("DHCP discovery: MAC address too short: %s", macaddress)
            return self.async_abort(reason="invalid_mac_address")
        
        mac_prefix = ":".join([mac_normalized[i:i+2] for i in range(0, 6, 2)])
        _LOGGER.debug("DHCP discovery: Extracted MAC prefix: %s", mac_prefix)
        
        # Check if MAC prefix matches Hikvision (prefixes are already uppercase in const)
        if mac_prefix not in HIKVISION_MAC_PREFIXES:
            _LOGGER.debug("DHCP discovery: MAC prefix %s not in Hikvision list (device not a Hikvision camera)", mac_prefix)
            return self.async_abort(reason="not_hikvision_device")
        
        _LOGGER.info("DHCP discovery: Found Hikvision device at %s (MAC: %s)", host, macaddress)
        
        # Use MAC address as unique_id for better device tracking
        await self.async_set_unique_id(mac_normalized)
        
        # Abort if already configured
        self._abort_if_unique_id_configured()
        
        # Store discovered host in context for use in user step
        self.context.update({"discovered_host": host})
        
        # Return form - this will show up in "Discovered" section
        # When user clicks "Configure", it will call async_step_user with the pre-filled values
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
