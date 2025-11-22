from homeassistant import config_entries
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL
from .const import DOMAIN


class HikvisionIsapiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Hikvision {user_input[CONF_HOST]}",
                data=user_input,
            )

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
