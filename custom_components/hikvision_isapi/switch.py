from __future__ import annotations
import logging
import requests
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hikvision_isapi"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    host = config[DOMAIN][CONF_HOST]
    user = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    add_entities([
        HikvisionTestSwitch(host, user, password)
    ], True)


class HikvisionTestSwitch(SwitchEntity):
    """A dummy switch to verify integration loads."""

    def __init__(self, host, user, password):
        self._host = host
        self._user = user
        self._password = password
        self._state = False

    @property
    def name(self):
        return "Hikvision Test Switch"

    @property
    def is_on(self):
        return self._state

    def turn_on(self, **kwargs):
        self._state = True
        _LOGGER.debug("Test switch turned ON")

    def turn_off(self, **kwargs):
        self._state = False
        _LOGGER.debug("Test switch turned OFF")
