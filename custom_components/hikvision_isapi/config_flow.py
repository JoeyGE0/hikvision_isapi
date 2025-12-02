"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries

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

    async def async_step_dhcp(self, discovery_info):
        """Handle DHCP discovery."""
        _LOGGER.debug("DHCP discovery triggered: %s", discovery_info)
        
        # Get IP address - try both 'ip' and 'hostname' attributes
        host = getattr(discovery_info, "ip", None) or getattr(discovery_info, "hostname", None)
        macaddress = getattr(discovery_info, "macaddress", None)
        
        if not host:
            _LOGGER.warning("DHCP discovery: No IP or hostname found in discovery_info")
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
        
        # Check if already configured (this will abort silently if already exists)
        # But we log it first so we can see in logs
        existing_entries = [
            entry for entry in self._async_current_entries()
            if entry.unique_id == mac_normalized
        ]
        if existing_entries:
            _LOGGER.debug("DHCP discovery: Device %s (MAC: %s) already configured, skipping", host, macaddress)
        
        self._abort_if_unique_id_configured()
        
        # Pre-fill the form with discovered IP
        return await self.async_step_user(
            {
                CONF_HOST: host,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "",
                CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
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

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
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
