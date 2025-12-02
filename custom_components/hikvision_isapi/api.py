"""API helper for Hikvision ISAPI."""
from __future__ import annotations

import logging
import re
import requests
import xml.etree.ElementTree as ET
from typing import Optional

_LOGGER = logging.getLogger(__name__)

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class HikvisionISAPI:
    """Helper class for Hikvision ISAPI calls."""

    def __init__(self, host: str, username: str, password: str, channel: int = 1):
        """Initialize the API helper."""
        self.host = host
        self.username = username
        self.password = password
        self.channel = channel
        self.base_url = f"http://{host}/ISAPI/Image/channels/{channel}"
        self._audio_session_url = f"http://{host}/ISAPI/System/TwoWayAudio/channels/{channel}/audioData"
        self._audio_session_id = None

    def _get(self, endpoint: str) -> ET.Element:
        """Make a GET request to ISAPI endpoint."""
        # Use full URL for System and Streaming endpoints, otherwise use base_url (Image channels)
        if endpoint.startswith("/ISAPI/System") or endpoint.startswith("/ISAPI/Streaming"):
            url = f"http://{self.host}{endpoint}"
        else:
            url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return ET.fromstring(response.text)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (401, 403):
                raise AuthenticationError(f"Authentication failed: {e}") from e
            _LOGGER.error("HTTP error GET %s: %s", endpoint, e)
            raise
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Request error GET %s: %s", endpoint, e)
            raise
        except Exception as e:
            _LOGGER.error("Failed to GET %s: %s", endpoint, e)
            raise

    def _put(self, endpoint: str, xml_data: str) -> ET.Element:
        """Make a PUT request to ISAPI endpoint."""
        url = f"http://{self.host}{endpoint}" if endpoint.startswith("/ISAPI/System") else f"{self.base_url}{endpoint}"
        try:
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return ET.fromstring(response.text)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (401, 403):
                raise AuthenticationError(f"Authentication failed: {e}") from e
            _LOGGER.error("HTTP error PUT %s: %s", endpoint, e)
            raise
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Request error PUT %s: %s", endpoint, e)
            raise
        except Exception as e:
            _LOGGER.error("Failed to PUT %s: %s", endpoint, e)
            raise

    def get_supplement_light(self) -> dict:
        """Get current supplement light settings."""
        try:
            xml = self._get("/supplementLight")
            result = {}
            
            mode = xml.find(f".//{XML_NS}supplementLightMode")
            if mode is not None:
                result["mode"] = mode.text.strip()
            
            white_bright = xml.find(f".//{XML_NS}whiteLightBrightness")
            if white_bright is not None:
                result["whiteLightBrightness"] = int(white_bright.text.strip())
            
            ir_bright = xml.find(f".//{XML_NS}irLightBrightness")
            if ir_bright is not None:
                result["irLightBrightness"] = int(ir_bright.text.strip())
            
            mixed_mode = xml.find(f".//{XML_NS}mixedLightBrightnessRegulatMode")
            if mixed_mode is not None:
                result["mixedLightBrightnessRegulatMode"] = mixed_mode.text.strip()
            
            brightness_mode = xml.find(f".//{XML_NS}brightnessRegulatMode")
            if brightness_mode is not None:
                result["brightnessRegulatMode"] = brightness_mode.text.strip()
            
            white_limit = xml.find(f".//{XML_NS}whiteLightbrightLimit")
            if white_limit is not None:
                result["whiteLightbrightLimit"] = int(white_limit.text.strip())
            
            ir_limit = xml.find(f".//{XML_NS}irLightbrightLimit")
            if ir_limit is not None:
                result["irLightbrightLimit"] = int(ir_limit.text.strip())
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get supplement light: %s", e)
            return {}

    def set_supplement_light(self, mode: str) -> bool:
        """Set supplement light mode (eventIntelligence/irLight/close)."""
        try:
            # Get current settings first to preserve other values
            current = self.get_supplement_light()
            if not current:
                return False
            
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace mode value
            xml_str = re.sub(
                r'<supplementLightMode>.*?</supplementLightMode>',
                f'<supplementLightMode>{mode}</supplementLightMode>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set supplement light: %s", e)
            return False

    def set_white_light_brightness(self, brightness: int) -> bool:
        """Set white light brightness (0-100)."""
        try:
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace whiteLightBrightness value
            xml_str = re.sub(
                r'<whiteLightBrightness>.*?</whiteLightBrightness>',
                f'<whiteLightBrightness>{brightness}</whiteLightBrightness>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set white light brightness: %s", e)
            return False

    def set_ir_light_brightness(self, brightness: int) -> bool:
        """Set IR light brightness (0-100)."""
        try:
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace irLightBrightness value
            xml_str = re.sub(
                r'<irLightBrightness>.*?</irLightBrightness>',
                f'<irLightBrightness>{brightness}</irLightBrightness>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set IR light brightness: %s", e)
            return False

    def set_brightness_control_mode(self, mode: str) -> bool:
        """Set light brightness control mode (auto/manual)."""
        try:
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text

            # Update both mixed and event-intelligence brightness control modes if present
            xml_str, count1 = re.subn(
                r"<brightnessRegulatMode>.*?</brightnessRegulatMode>",
                f"<brightnessRegulatMode>{mode}</brightnessRegulatMode>",
                xml_str,
            )
            xml_str, count2 = re.subn(
                r"<mixedLightBrightnessRegulatMode>.*?</mixedLightBrightnessRegulatMode>",
                f"<mixedLightBrightnessRegulatMode>{mode}</mixedLightBrightnessRegulatMode>",
                xml_str,
            )

            if count1 == 0 and count2 == 0:
                _LOGGER.error("Brightness control fields not found in supplementLight XML")
                return False

            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set brightness control mode: %s", e)
            return False

    def set_white_light_brightness_limit(self, limit: int) -> bool:
        """Set white light brightness limit (0-100)."""
        try:
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text

            xml_str, count = re.subn(
                r"<whiteLightbrightLimit>.*?</whiteLightbrightLimit>",
                f"<whiteLightbrightLimit>{limit}</whiteLightbrightLimit>",
                xml_str,
            )
            if count == 0:
                _LOGGER.error("whiteLightbrightLimit field not found in supplementLight XML")
                return False

            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set white light brightness limit: %s", e)
            return False

    def set_ir_light_brightness_limit(self, limit: int) -> bool:
        """Set IR light brightness limit (0-100)."""
        try:
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text

            xml_str, count = re.subn(
                r"<irLightbrightLimit>.*?</irLightbrightLimit>",
                f"<irLightbrightLimit>{limit}</irLightbrightLimit>",
                xml_str,
            )
            if count == 0:
                _LOGGER.error("irLightbrightLimit field not found in supplementLight XML")
                return False

            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5,
            )
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set IR light brightness limit: %s", e)
            return False

    def get_white_light_time(self) -> Optional[int]:
        """Get white light duration (10-300 seconds)."""
        try:
            xml = self._get("/supplementLight")
            time_elem = xml.find(f".//{XML_NS}whiteLightTime")
            if time_elem is not None and time_elem.text:
                return int(time_elem.text.strip())
            return None
        except Exception as e:
            _LOGGER.error("Failed to get white light time: %s", e)
            return None

    def set_white_light_time(self, duration: int) -> bool:
        """Set white light duration (10-300 seconds)."""
        try:
            # Get current settings first
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/supplementLight"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace whiteLightTime value
            xml_str = re.sub(
                r'<whiteLightTime>.*?</whiteLightTime>',
                f'<whiteLightTime>{duration}</whiteLightTime>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set white light time: %s", e)
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
            xml = self._get("/ISAPI/System/deviceInfo")
            
            device_info = {}
            device_info["deviceName"] = xml.find(f".//{XML_NS}deviceName")
            device_info["model"] = xml.find(f".//{XML_NS}model")
            device_info["serialNumber"] = xml.find(f".//{XML_NS}serialNumber")
            device_info["firmwareVersion"] = xml.find(f".//{XML_NS}firmwareVersion")
            device_info["hardwareVersion"] = xml.find(f".//{XML_NS}hardwareVersion")
            device_info["macAddress"] = xml.find(f".//{XML_NS}macAddress")
            device_info["deviceID"] = xml.find(f".//{XML_NS}deviceID")
            device_info["manufacturer"] = xml.find(f".//{XML_NS}manufacturer")
            
            # Extract text values
            result = {}
            for key, element in device_info.items():
                if element is not None and element.text:
                    result[key] = element.text.strip()
            
            return result
        except Exception as e:
            _LOGGER.error("Failed to get device info: %s", e)
            return {}

    def get_two_way_audio(self) -> dict:
        """Get two-way audio settings."""
        try:
            xml = self._get("/ISAPI/System/TwoWayAudio/channels/1")
            
            result = {}
            result["enabled"] = xml.find(f".//{XML_NS}enabled")
            result["speakerVolume"] = xml.find(f".//{XML_NS}speakerVolume")
            result["microphoneVolume"] = xml.find(f".//{XML_NS}microphoneVolume")
            result["audioCompressionType"] = xml.find(f".//{XML_NS}audioCompressionType")
            result["noisereduce"] = xml.find(f".//{XML_NS}noisereduce")
            
            # Extract text values
            audio_info = {}
            for key, element in result.items():
                if element is not None and element.text:
                    if key in ["enabled", "noisereduce"]:
                        audio_info[key] = element.text.strip().lower() == "true"
                    elif key in ["speakerVolume", "microphoneVolume"]:
                        audio_info[key] = int(element.text.strip())
                    else:
                        audio_info[key] = element.text.strip()
            
            return audio_info
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get two-way audio: %s", e)
            return {}

    def set_speaker_volume(self, volume: int) -> bool:
        """Set speaker volume (0-100)."""
        try:
            # Get current settings first
            current = self.get_two_way_audio()
            if not current:
                return False
            
            # Build full XML with all required fields
            enabled = "true" if current.get("enabled", False) else "false"
            mic_volume = current.get("microphoneVolume", 100)
            compression = current.get("audioCompressionType", "G.711ulaw")
            noise_reduce = "true"  # Default
            
            xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>{enabled}</enabled>
<audioCompressionType>{compression}</audioCompressionType>
<speakerVolume>{volume}</speakerVolume>
<microphoneVolume>{mic_volume}</microphoneVolume>
<noisereduce>{noise_reduce}</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
            
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set speaker volume: %s", e)
            return False

    def set_microphone_volume(self, volume: int) -> bool:
        """Set microphone volume (0-100)."""
        try:
            # Get current settings first
            current = self.get_two_way_audio()
            if not current:
                return False
            
            # Build full XML with all required fields
            enabled = "true" if current.get("enabled", False) else "false"
            speaker_volume = current.get("speakerVolume", 50)
            compression = current.get("audioCompressionType", "G.711ulaw")
            noise_reduce = "true"  # Default
            
            xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>{enabled}</enabled>
<audioCompressionType>{compression}</audioCompressionType>
<speakerVolume>{speaker_volume}</speakerVolume>
<microphoneVolume>{volume}</microphoneVolume>
<noisereduce>{noise_reduce}</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
            
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set microphone volume: %s", e)
            return False

    def set_noisereduce(self, enabled: bool) -> bool:
        """Enable/disable noise reduction."""
        try:
            # Get current settings first
            current = self.get_two_way_audio()
            if not current:
                return False
            
            # Build full XML with all required fields
            audio_enabled = "true" if current.get("enabled", False) else "false"
            speaker_volume = current.get("speakerVolume", 50)
            mic_volume = current.get("microphoneVolume", 100)
            compression = current.get("audioCompressionType", "G.711ulaw")
            noise_reduce = "true" if enabled else "false"
            
            xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>{audio_enabled}</enabled>
<audioCompressionType>{compression}</audioCompressionType>
<speakerVolume>{speaker_volume}</speakerVolume>
<microphoneVolume>{mic_volume}</microphoneVolume>
<noisereduce>{noise_reduce}</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
            
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set noise reduction: %s", e)
            return False

    def open_audio_session(self) -> Optional[str]:
        """Open two-way audio session. Returns sessionId."""
        try:
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1/open"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            session_id = xml.find(f".//{XML_NS}sessionId")
            return session_id.text.strip() if session_id is not None else None
        except Exception as e:
            _LOGGER.error("Failed to open audio session: %s", e)
            return None

    def close_audio_session(self) -> bool:
        """Close two-way audio session."""
        try:
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1/close"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to close audio session: %s", e)
            return False

    def play_test_tone(self) -> bool:
        """Play a 2-second test tone (for testing purposes)."""
        import time
        import math
        
        try:
            # Step 1: Close any existing sessions
            _LOGGER.info("Closing any existing audio sessions...")
            self.close_audio_session()
            time.sleep(0.5)
            
            # Step 2: Enable two-way audio
            _LOGGER.info("Enabling two-way audio...")
            xml_data = """<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>true</enabled>
<audioCompressionType>G.711ulaw</audioCompressionType>
<speakerVolume>100</speakerVolume>
<microphoneVolume>100</microphoneVolume>
<noisereduce>true</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
            url = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_data,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            time.sleep(0.5)
            
            # Step 3: Open session
            _LOGGER.info("Opening audio session...")
            session_id = self.open_audio_session()
            if not session_id:
                _LOGGER.error("Failed to open audio session")
                return False
            
            # Step 4: Generate 2-second siren sound
            _LOGGER.info("Generating 2-second siren sound...")
            sample_rate = 8000
            duration = 2.0
            num_samples = int(sample_rate * duration)
            
            # Siren parameters: alternate between low and high frequencies
            low_freq = 600   # Lower siren frequency (Hz)
            high_freq = 1200  # Higher siren frequency (Hz)
            cycle_duration = 0.3  # How long each "wee" or "woo" lasts (seconds)
            cycles_per_second = 1.0 / cycle_duration  # How many cycles per second
            
            def linear_to_ulaw(linear):
                linear = max(-32768, min(32767, linear))
                sign = 0 if linear >= 0 else 0x80
                linear = abs(linear)
                exp = 0
                if linear >= 256:
                    if linear >= 1024:
                        if linear >= 4096:
                            if linear >= 16384:
                                exp = 7
                            else:
                                exp = 6
                        else:
                            exp = 5
                    else:
                        exp = 4
                else:
                    if linear >= 16:
                        if linear >= 64:
                            exp = 3
                        else:
                            exp = 2
                    else:
                        if linear >= 4:
                            exp = 1
                        else:
                            exp = 0
                mantissa = (linear >> (exp + 3)) & 0x0F
                ulaw = sign | (exp << 4) | mantissa
                return (~ulaw) & 0xFF
            
            ulaw_data = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                
                # Calculate which part of the cycle we're in (0-1)
                cycle_position = (t * cycles_per_second) % 1.0
                
                # Alternate between low and high frequency
                # First half of cycle: low to high (wee)
                # Second half of cycle: high to low (woo)
                if cycle_position < 0.5:
                    # Rising: low to high
                    freq = low_freq + (high_freq - low_freq) * (cycle_position * 2)
                else:
                    # Falling: high to low
                    freq = high_freq - (high_freq - low_freq) * ((cycle_position - 0.5) * 2)
                
                # Generate sine wave at current frequency
                sample = math.sin(2 * math.pi * freq * t)
                pcm_sample = int(sample * 32767)
                ulaw_byte = linear_to_ulaw(pcm_sample)
                ulaw_data.append(ulaw_byte)
            
            _LOGGER.info("Generated %d bytes of audio", len(ulaw_data))
            
            # Step 5: Send all audio in one request
            _LOGGER.info("Sending audio to camera...")
            endpoint = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1/audioData"
            response = requests.put(
                endpoint,
                auth=(self.username, self.password),
                data=bytes(ulaw_data),
                verify=False,
                timeout=10
            )
            
            if response.status_code != 200:
                _LOGGER.error("Failed to send audio: %s", response.text[:300])
                self.close_audio_session()
                return False
            
            _LOGGER.info("Test tone sent successfully!")
            
            # Step 6: Close session
            self.close_audio_session()
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to play test tone: %s", e, exc_info=True)
            try:
                self.close_audio_session()
            except:
                pass
            return False

    def get_motion_detection(self) -> dict:
        """Get motion detection settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/motionDetection"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            # Get sensitivity from MotionDetectionLayout
            layout = xml.find(f".//{XML_NS}MotionDetectionLayout")
            if layout is not None:
                sensitivity = layout.find(f".//{XML_NS}sensitivityLevel")
                if sensitivity is not None:
                    result["sensitivityLevel"] = int(sensitivity.text.strip())
                
                target_type = layout.find(f".//{XML_NS}targetType")
                if target_type is not None:
                    result["targetType"] = target_type.text.strip()
            
            # Get trigger times
            start_time = xml.find(f".//{XML_NS}startTriggerTime")
            if start_time is not None:
                result["startTriggerTime"] = int(start_time.text.strip())
            
            end_time = xml.find(f".//{XML_NS}endTriggerTime")
            if end_time is not None:
                result["endTriggerTime"] = int(end_time.text.strip())
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get motion detection: %s", e)
            return {}

    def set_motion_detection(self, enabled: bool) -> bool:
        """Enable/disable motion detection."""
        try:
            # Get current settings first
            current = self.get_motion_detection()
            if not current:
                return False
            
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/motionDetection"
            
            # Get full XML to preserve other settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace enabled value
            import re
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set motion detection: %s", e)
            return False

    def set_motion_sensitivity(self, sensitivity: int) -> bool:
        """Set motion detection sensitivity (0-100)."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/motionDetection"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace sensitivityLevel value
            xml_str = re.sub(
                r'<sensitivityLevel>.*?</sensitivityLevel>',
                f'<sensitivityLevel>{sensitivity}</sensitivityLevel>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set motion sensitivity: %s", e)
            return False

    def set_motion_target_type(self, target_type: str) -> bool:
        """Set motion detection target type (human, vehicle, human,vehicle)."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/motionDetection"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace targetType value
            xml_str = re.sub(
                r'<targetType>.*?</targetType>',
                f'<targetType>{target_type}</targetType>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set motion target type: %s", e)
            return False

    def set_motion_trigger_times(self, start_time: int, end_time: int) -> bool:
        """Set motion detection trigger times (milliseconds)."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/motionDetection"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace trigger time values
            xml_str = re.sub(
                r'<startTriggerTime>.*?</startTriggerTime>',
                f'<startTriggerTime>{start_time}</startTriggerTime>',
                xml_str
            )
            xml_str = re.sub(
                r'<endTriggerTime>.*?</endTriggerTime>',
                f'<endTriggerTime>{end_time}</endTriggerTime>',
                xml_str
            )
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set motion trigger times: %s", e)
            return False

    def get_tamper_detection(self) -> dict:
        """Get tamper detection settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/tamperDetection"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get tamper detection: %s", e)
            return {}

    def set_tamper_detection(self, enabled: bool) -> bool:
        """Enable/disable tamper detection."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/tamperDetection"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            
            # Replace enabled value
            import re
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set tamper detection: %s", e)
            return False

    def get_snapshot(self) -> Optional[bytes]:
        """Get camera snapshot image."""
        try:
            url = f"http://{self.host}/ISAPI/Streaming/channels/101/picture"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            _LOGGER.error("Failed to get snapshot: %s", e)
            return None

    def get_streaming_status(self) -> dict:
        """Get streaming status information."""
        try:
            xml = self._get("/ISAPI/Streaming/status")
            
            result = {}
            
            # Total streaming sessions
            total = xml.find(f".//{XML_NS}totalStreamingSessions")
            if total is not None:
                result["totalStreamingSessions"] = int(total.text.strip())
            
            # Client addresses
            clients = xml.findall(f".//{XML_NS}StreamingSessionStatus")
            client_ips = []
            for client in clients:
                # IP address is nested under clientAddress
                client_addr = client.find(f".//{XML_NS}clientAddress")
                if client_addr is not None:
                    ip_elem = client_addr.find(f".//{XML_NS}ipAddress")
                    if ip_elem is not None:
                        client_ips.append(ip_elem.text.strip())
            result["clientAddresses"] = ", ".join(client_ips) if client_ips else "None"
            result["clientCount"] = len(client_ips)
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get streaming status: %s", e)
            return {}

    def get_system_status(self) -> dict:
        """Get system status information."""
        try:
            xml = self._get("/ISAPI/System/status")
            
            result = {}
            
            # CPU
            cpu_util = xml.find(f".//{XML_NS}cpuUtilization")
            if cpu_util is not None:
                result["cpu_utilization"] = int(cpu_util.text.strip())
            
            # Memory
            mem_usage = xml.find(f".//{XML_NS}memoryUsage")
            if mem_usage is not None:
                result["memory_usage"] = int(mem_usage.text.strip())
            
            mem_avail = xml.find(f".//{XML_NS}memoryAvailable")
            if mem_avail is not None:
                result["memory_available"] = int(mem_avail.text.strip())
            
            # Uptime
            uptime = xml.find(f".//{XML_NS}deviceUpTime")
            if uptime is not None:
                result["uptime"] = int(uptime.text.strip())
            
            # Reboot count
            reboot_count = xml.find(f".//{XML_NS}totalRebootCount")
            if reboot_count is not None:
                result["reboot_count"] = int(reboot_count.text.strip())
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to get system status: %s", e)
            return {}

    def get_field_detection(self) -> dict:
        """Get field detection (intrusion) settings."""
        try:
            xml = self._get("/ISAPI/Smart/FieldDetection")
            result = {}
            field = xml.find(f".//{XML_NS}FieldDetection")
            if field is not None:
                enabled = field.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            return result
        except Exception as e:
            _LOGGER.error("Failed to get field detection: %s", e)
            return {}

    def set_field_detection(self, enabled: bool) -> bool:
        """Enable/disable field detection (intrusion)."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/FieldDetection"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set field detection: %s", e)
            return False

    def get_line_detection(self) -> dict:
        """Get line detection settings."""
        try:
            xml = self._get("/ISAPI/Smart/LineDetection")
            result = {}
            line = xml.find(f".//{XML_NS}LineDetection")
            if line is not None:
                enabled = line.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            return result
        except Exception as e:
            _LOGGER.error("Failed to get line detection: %s", e)
            return {}

    def set_line_detection(self, enabled: bool) -> bool:
        """Enable/disable line detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/LineDetection"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set line detection: %s", e)
            return False

    def get_scene_change_detection(self) -> dict:
        """Get scene change detection settings."""
        try:
            xml = self._get("/ISAPI/Smart/SceneChangeDetection")
            result = {}
            scene = xml.find(f".//{XML_NS}SceneChangeDetection")
            if scene is not None:
                enabled = scene.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            return result
        except Exception as e:
            _LOGGER.error("Failed to get scene change detection: %s", e)
            return {}

    def set_scene_change_detection(self, enabled: bool) -> bool:
        """Enable/disable scene change detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/SceneChangeDetection"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set scene change detection: %s", e)
            return False

    def get_region_entrance(self) -> dict:
        """Get region entrance detection settings."""
        try:
            xml = self._get("/ISAPI/Smart/regionEntrance")
            result = {}
            region = xml.find(f".//{XML_NS}RegionEntrance")
            if region is not None:
                enabled = region.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            return result
        except Exception as e:
            _LOGGER.error("Failed to get region entrance: %s", e)
            return {}

    def set_region_entrance(self, enabled: bool) -> bool:
        """Enable/disable region entrance detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/regionEntrance"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set region entrance: %s", e)
            return False

    def get_region_exiting(self) -> dict:
        """Get region exiting detection settings."""
        try:
            xml = self._get("/ISAPI/Smart/regionExiting")
            result = {}
            region = xml.find(f".//{XML_NS}RegionExiting")
            if region is not None:
                enabled = region.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            return result
        except Exception as e:
            _LOGGER.error("Failed to get region exiting: %s", e)
            return {}

    def set_region_exiting(self, enabled: bool) -> bool:
        """Enable/disable region exiting detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/regionExiting"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            xml_str = response.text
            enabled_str = "true" if enabled else "false"
            xml_str = re.sub(r'<enabled>.*?</enabled>', f'<enabled>{enabled_str}</enabled>', xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden - user '{self.username}' may not have required permissions (403)")
            response.raise_for_status()
            return True
        except AuthenticationError:
            raise
        except Exception as e:
            _LOGGER.error("Failed to set region exiting: %s", e)
            return False

    def restart(self) -> bool:
        """Restart the camera."""
        try:
            url = f"http://{self.host}/ISAPI/System/reboot"
            response = requests.put(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to restart camera: %s", e)
            return False
