"""API helper for Hikvision ISAPI calls."""
import logging
import requests
import xml.etree.ElementTree as ET
from typing import Optional

_LOGGER = logging.getLogger(__name__)

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"


class HikvisionISAPI:
    """Helper class for Hikvision ISAPI calls."""

    def __init__(self, host: str, username: str, password: str, channel: int = 1):
        """Initialize the API helper."""
        self.host = host
        self.username = username
        self.password = password
        self.channel = channel
        self.base_url = f"http://{host}/ISAPI/Image/channels/{channel}"

    def _get(self, endpoint: str) -> ET.Element:
        """Make a GET request to ISAPI endpoint."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as e:
            _LOGGER.error("Failed to GET %s: %s", endpoint, e)
            raise

    def _put(self, endpoint: str, xml_data: str) -> ET.Element:
        """Make a PUT request to ISAPI endpoint."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as e:
            _LOGGER.error("Failed to PUT %s: %s", endpoint, e)
            raise

    def get_supplement_light(self) -> Optional[str]:
        """Get current supplement light mode."""
        try:
            xml = self._get("/supplementLight")
            mode = xml.find(f".//{XML_NS}supplementLightMode")
            return mode.text.strip() if mode is not None else None
        except Exception as e:
            _LOGGER.error("Failed to get supplement light: %s", e)
            return None

    def set_supplement_light(self, mode: str) -> bool:
        """Set supplement light mode (eventIntelligence/irLight/close)."""
        xml_data = f"<SupplementLight><supplementLightMode>{mode}</supplementLightMode></SupplementLight>"
        try:
            self._put("/supplementLight", xml_data)
            return True
        except Exception as e:
            _LOGGER.error("Failed to set supplement light: %s", e)
            return False

    def get_ircut_filter(self) -> dict:
        """Get IR cut filter settings."""
        try:
            xml = self._get("/IrcutFilter")
            result = {}
            
            mode = xml.find(f".//{XML_NS}IrcutFilterType")
            if mode is not None:
                result["mode"] = mode.text.strip()
            
            sensitivity = xml.find(f".//{XML_NS}nightToDayFilterLevel")
            if sensitivity is not None:
                result["sensitivity"] = int(sensitivity.text.strip())
            
            filter_time = xml.find(f".//{XML_NS}nightToDayFilterTime")
            if filter_time is not None:
                result["filter_time"] = int(filter_time.text.strip())
            
            return result
        except Exception as e:
            _LOGGER.error("Failed to get IR cut filter: %s", e)
            return {}

    def set_ircut_mode(self, mode: str) -> bool:
        """Set IR cut mode (auto/day/night)."""
        xml_data = f"<IrcutFilter><IrcutFilterType>{mode}</IrcutFilterType></IrcutFilter>"
        try:
            self._put("/IrcutFilter", xml_data)
            return True
        except Exception as e:
            _LOGGER.error("Failed to set IR cut mode: %s", e)
            return False

    def set_ircut_sensitivity(self, sensitivity: int) -> bool:
        """Set IR sensitivity (0-7)."""
        xml_data = f"<IrcutFilter><nightToDayFilterLevel>{sensitivity}</nightToDayFilterLevel></IrcutFilter>"
        try:
            self._put("/IrcutFilter", xml_data)
            return True
        except Exception as e:
            _LOGGER.error("Failed to set IR sensitivity: %s", e)
            return False

    def set_ircut_filter_time(self, filter_time: int) -> bool:
        """Set IR filter time (5-120 seconds)."""
        xml_data = f"<IrcutFilter><nightToDayFilterTime>{filter_time}</nightToDayFilterTime></IrcutFilter>"
        try:
            self._put("/IrcutFilter", xml_data)
            return True
        except Exception as e:
            _LOGGER.error("Failed to set IR filter time: %s", e)
            return False

    def get_device_info(self) -> dict:
        """Get device information from ISAPI."""
        try:
            url = f"http://{self.host}/ISAPI/System/deviceInfo"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            device_info = {}
            device_info["deviceName"] = xml.find(f".//{XML_NS}deviceName")
            device_info["model"] = xml.find(f".//{XML_NS}model")
            device_info["serialNumber"] = xml.find(f".//{XML_NS}serialNumber")
            device_info["firmwareVersion"] = xml.find(f".//{XML_NS}firmwareVersion")
            device_info["hardwareVersion"] = xml.find(f".//{XML_NS}hardwareVersion")
            
            # Extract text values
            result = {}
            for key, element in device_info.items():
                if element is not None and element.text:
                    result[key] = element.text.strip()
            
            return result
        except Exception as e:
            _LOGGER.error("Failed to get device info: %s", e)
            return {}

