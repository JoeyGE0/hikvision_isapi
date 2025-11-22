import logging
import requests
import xml.etree.ElementTree as ET

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    config = hass.data[DOMAIN][entry.entry_id]

    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    entities = [
        HikvisionIRCutSensor(host, username, password),
    ]

    async_add_entities(entities, True)


class HikvisionIRCutSensor(SensorEntity):
    """IR Cut filter mode sensor"""

    _attr_name = "Hikvision IR Cut Mode"
    _attr_unique_id = "hikvision_ircut_mode"

    def __init__(self, host, username, password):
        self._host = host
        self._username = username
        self._password = password
        self._state = None

    @property
    def native_value(self):
        return self._state

    def update(self):
        url = f"http://{self._host}/ISAPI/Image/channels/1/IrcutFilter"

        try:
            r = requests.get(
                url,
                auth=(self._username, self._password),
                verify=False,
                timeout=5
            )
            xml = ET.fromstring(r.text)

            mode = xml.find(".//{http://www.hikvision.com/ver20/XMLSchema}IrcutFilterType")

            self._state = mode.text.strip() if mode is not None else "unknown"

        except Exception as e:
            _LOGGER.error("Failed updating IR Cut sensor: %s", e)
            self._state = "error"
