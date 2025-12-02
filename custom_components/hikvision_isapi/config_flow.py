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
