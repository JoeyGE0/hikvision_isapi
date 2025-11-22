"""Config flow for the Hikvision ISAPI integration."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL

DATA_SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("username"): str,
    vol.Required("password"): str,
    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=300)
    ),
})

class HikvisionISAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = 1
    STEP_USER = "user"

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # TODO: try connecting to camera/api to validate credentials
            # if fails:
            #   errors["base"] = "cannot_connect"
            # else:
            return self.async_create_entry(title=user_input["host"], data=user_input)

        return self.async_show_form(
            step_id=self.STEP_USER, data_schema=DATA_SCHEMA, errors=errors
        )
