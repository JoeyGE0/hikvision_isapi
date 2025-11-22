"""API helper for Hikvision ISAPI."""
from __future__ import annotations

import logging
import re
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
        self._audio_session_url = f"http://{host}/ISAPI/System/TwoWayAudio/channels/{channel}/audioData"
        self._audio_session_id = None

    def _get(self, endpoint: str) -> ET.Element:
        """Make a GET request to ISAPI endpoint."""
        url = f"http://{self.host}{endpoint}" if endpoint.startswith("/ISAPI/System") else f"{self.base_url}{endpoint}"
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
            response.raise_for_status()
            return True
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
            
            # Extract text values
            audio_info = {}
            for key, element in result.items():
                if element is not None and element.text:
                    if key == "enabled":
                        audio_info[key] = element.text.strip().lower() == "true"
                    elif key in ["speakerVolume", "microphoneVolume"]:
                        audio_info[key] = int(element.text.strip())
                    else:
                        audio_info[key] = element.text.strip()
            
            return audio_info
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
            response.raise_for_status()
            return True
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
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to set microphone volume: %s", e)
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
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
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
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to set motion detection: %s", e)
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
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
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
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to set tamper detection: %s", e)
            return False

    def get_alarm_input(self, input_id: int = 1) -> dict:
        """Get alarm input settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/inputs/{input_id}"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
        except Exception as e:
            _LOGGER.error("Failed to get alarm input %d: %s", input_id, e)
            return {}

    def set_alarm_input(self, input_id: int = 1, enabled: bool = True) -> bool:
        """Enable/disable alarm input."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/inputs/{input_id}"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml_str = response.text
            
            # Replace enabled value
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
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to set alarm input %d: %s", input_id, e)
            return False

    def get_alarm_output(self, output_id: int = 1) -> dict:
        """Get alarm output settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/outputs/{output_id}"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            # Alarm output doesn't have enabled, but we can check normalStatus
            normal_status = xml.find(f".//{XML_NS}normalStatus")
            if normal_status is not None:
                # "open" means enabled, "close" means disabled
                result["enabled"] = normal_status.text.strip().lower() == "open"
            
            return result
        except Exception as e:
            _LOGGER.error("Failed to get alarm output %d: %s", output_id, e)
            return {}

    def set_alarm_output(self, output_id: int = 1, enabled: bool = True) -> bool:
        """Enable/disable alarm output."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/outputs/{output_id}"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml_str = response.text
            
            # Replace normalStatus value (open = enabled, close = disabled)
            status_str = "open" if enabled else "close"
            xml_str = re.sub(r'<normalStatus>.*?</normalStatus>', f'<normalStatus>{status_str}</normalStatus>', xml_str)
            
            # PUT updated XML
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.error("Failed to set alarm output %d: %s", output_id, e)
            return False

    def _get_detection(self, detection_type: str) -> dict:
        """Generic method to get detection settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/{detection_type}"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            
            result = {}
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
        except Exception as e:
            _LOGGER.debug("Failed to get %s: %s", detection_type, e)
            return {}

    def _set_detection(self, detection_type: str, enabled: bool) -> bool:
        """Generic method to set detection settings."""
        try:
            url = f"http://{self.host}/ISAPI/System/Video/inputs/channels/{self.channel}/{detection_type}"
            
            # Get current settings
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            xml_str = response.text
            
            # Replace enabled value
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
            response.raise_for_status()
            return True
        except Exception as e:
            _LOGGER.debug("Failed to set %s: %s", detection_type, e)
            return False

    def get_intrusion_detection(self) -> dict:
        """Get intrusion detection settings."""
        return self._get_detection("intrusionDetection")

    def set_intrusion_detection(self, enabled: bool) -> bool:
        """Enable/disable intrusion detection."""
        return self._set_detection("intrusionDetection", enabled)

    def get_line_crossing_detection(self) -> dict:
        """Get line crossing detection settings."""
        return self._get_detection("lineDetection")

    def set_line_crossing_detection(self, enabled: bool) -> bool:
        """Enable/disable line crossing detection."""
        return self._set_detection("lineDetection", enabled)

    def get_region_entrance_detection(self) -> dict:
        """Get region entrance detection settings."""
        return self._get_detection("regionEntranceDetection")

    def set_region_entrance_detection(self, enabled: bool) -> bool:
        """Enable/disable region entrance detection."""
        return self._set_detection("regionEntranceDetection", enabled)

    def get_region_exiting_detection(self) -> dict:
        """Get region exiting detection settings."""
        return self._get_detection("regionExitingDetection")

    def set_region_exiting_detection(self, enabled: bool) -> bool:
        """Enable/disable region exiting detection."""
        return self._set_detection("regionExitingDetection", enabled)

    def get_scene_change_detection(self) -> dict:
        """Get scene change detection settings."""
        return self._get_detection("sceneChangeDetection")

    def set_scene_change_detection(self, enabled: bool) -> bool:
        """Enable/disable scene change detection."""
        return self._set_detection("sceneChangeDetection", enabled)

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
