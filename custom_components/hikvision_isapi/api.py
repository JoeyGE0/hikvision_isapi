"""API helper for Hikvision ISAPI."""
from __future__ import annotations

import logging
import re
import requests
import json
import xml.etree.ElementTree as ET
from typing import Optional

_LOGGER = logging.getLogger(__name__)

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"


def _extract_error_message(response) -> str:
    """Extract error message from camera response (XML or JSON)."""
    try:
        text = response.text
        if not text:
            return ""
        
        # Try JSON first
        try:
            data = json.loads(text)
            # Check common JSON error fields (statusString is user-friendly summary, errorMsg is detailed)
            if isinstance(data, dict):
                status_string = data.get("ResponseStatus", {}).get("statusString") or data.get("statusString") or ""
                error_msg = data.get("errorMsg") or ""
                
                # Prefer statusString if it's meaningful, otherwise use errorMsg
                if status_string and status_string.strip():
                    # If we also have errorMsg, try to find a relevant part
                    if error_msg:
                        # Look for common error patterns in errorMsg
                        error_parts = [e.strip() for e in error_msg.split(";") if e.strip()]
                        # Filter for relevant errors (not just technical details)
                        relevant_errors = []
                        for e in error_parts:
                            e_lower = e.lower()
                            # Check for specific patterns
                            if "remain_path=audiodata" in e_lower or "remain_path=audio" in e_lower:
                                relevant_errors.append("Two-way audio is in progress")
                            elif any(keyword in e_lower for keyword in [
                                "two-way audio", "busy", "in progress", 
                                "not support", "not allowed", "permission", "forbidden"
                            ]):
                                relevant_errors.append(e)
                        
                        if relevant_errors:
                            return f"{status_string}: {relevant_errors[0]}"
                    return status_string
                elif error_msg and error_msg.strip():
                    # Clean up errorMsg - it can be very long with multiple errors separated by semicolons
                    errors = [e.strip() for e in error_msg.split(";") if e.strip()]
                    if errors:
                        # Return first error, or first 200 chars if single long error
                        result = errors[0] if len(errors[0]) < 200 else errors[0][:200]
                        if len(errors) > 1:
                            result += f" (+{len(errors)-1} more)"
                        return result
                
                # Fallback to other fields
                other_msg = data.get("errorMessage") or data.get("message") or data.get("error") or ""
                if other_msg and other_msg.strip() and other_msg != "{}":
                    return other_msg
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try XML
        try:
            root = ET.fromstring(text)
            # Check common XML error elements
            for ns in [XML_NS, "{http://www.isapi.org/ver20/XMLSchema}", ""]:
                status_string = root.find(f".//{ns}statusString")
                if status_string is not None and status_string.text:
                    return status_string.text.strip()
                error_msg = root.find(f".//{ns}errorMessage")
                if error_msg is not None and error_msg.text:
                    return error_msg.text.strip()
        except ET.ParseError:
            pass
        
        # Fallback: return first 200 chars of response
        return text[:200].strip() if text else ""
    except Exception:
        return ""


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
        self.device_info = {}
        self.capabilities = {}
        self.cameras = []  # List of discovered cameras/channels

    def _get(self, endpoint: str) -> ET.Element:
        """Make a GET request to ISAPI endpoint."""
        # Use full URL for System, Streaming, Smart, Security, and Event endpoints, otherwise use base_url (Image channels)
        if (endpoint.startswith("/ISAPI/System") or endpoint.startswith("/ISAPI/Streaming") or 
            endpoint.startswith("/ISAPI/Smart") or endpoint.startswith("/ISAPI/Security") or
            endpoint.startswith("/ISAPI/Event")):
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
            # Connection errors are expected during camera restarts - log as warning
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Connection error GET %s (camera may be restarting): %s", endpoint, e)
            else:
                _LOGGER.error("Request error GET %s: %s", endpoint, e)
            raise
        except Exception as e:
            _LOGGER.error("Failed to GET %s: %s", endpoint, e)
            raise

    def _put(self, endpoint: str, xml_data: str) -> ET.Element:
        """Make a PUT request to ISAPI endpoint."""
        # Use full URL for System, Streaming, Smart, Security, and Event endpoints, otherwise use base_url (Image channels)
        if (endpoint.startswith("/ISAPI/System") or endpoint.startswith("/ISAPI/Streaming") or 
            endpoint.startswith("/ISAPI/Smart") or endpoint.startswith("/ISAPI/Security") or
            endpoint.startswith("/ISAPI/Event")):
            url = f"http://{self.host}{endpoint}"
        else:
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get supplement light (camera may be restarting): %s", e)
            else:
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get white light time (camera may be restarting): %s", e)
            else:
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get IR cut filter (camera may be restarting): %s", e)
            else:
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

    def get_color(self) -> dict:
        """Get color settings (brightness, contrast, saturation)."""
        try:
            xml = self._get("/color")
            result = {}
            
            brightness = xml.find(f".//{XML_NS}brightnessLevel")
            if brightness is not None:
                result["brightness"] = int(brightness.text.strip())
            
            contrast = xml.find(f".//{XML_NS}contrastLevel")
            if contrast is not None:
                result["contrast"] = int(contrast.text.strip())
            
            saturation = xml.find(f".//{XML_NS}saturationLevel")
            if saturation is not None:
                result["saturation"] = int(saturation.text.strip())
            
            return result
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get color settings (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get color settings: %s", e)
            return {}

    def set_brightness(self, brightness: int) -> bool:
        """Set brightness level (0-100)."""
        try:
            # Get current settings first
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/color"
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
            
            # Replace brightnessLevel value
            xml_str = re.sub(
                r'<brightnessLevel>.*?</brightnessLevel>',
                f'<brightnessLevel>{brightness}</brightnessLevel>',
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
            _LOGGER.error("Failed to set brightness: %s", e)
            return False

    def set_contrast(self, contrast: int) -> bool:
        """Set contrast level (0-100)."""
        try:
            # Get current settings first
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/color"
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
            
            # Replace contrastLevel value
            xml_str = re.sub(
                r'<contrastLevel>.*?</contrastLevel>',
                f'<contrastLevel>{contrast}</contrastLevel>',
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
            _LOGGER.error("Failed to set contrast: %s", e)
            return False

    def set_saturation(self, saturation: int) -> bool:
        """Set saturation level (0-100)."""
        try:
            # Get current settings first
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}/color"
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
            
            # Replace saturationLevel value
            xml_str = re.sub(
                r'<saturationLevel>.*?</saturationLevel>',
                f'<saturationLevel>{saturation}</saturationLevel>',
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
            _LOGGER.error("Failed to set saturation: %s", e)
            return False

    def get_sharpness(self) -> Optional[int]:
        """Get sharpness level (0-100)."""
        try:
            xml = self._get("")
            sharpness_elem = xml.find(f".//{XML_NS}Sharpness")
            if sharpness_elem is not None:
                level_elem = sharpness_elem.find(f".//{XML_NS}SharpnessLevel")
                if level_elem is not None and level_elem.text:
                    return int(level_elem.text.strip())
            return None
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get sharpness (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get sharpness: %s", e)
            return None

    def set_sharpness(self, sharpness: int) -> bool:
        """Set sharpness level (0-100)."""
        try:
            # Get current settings first
            url = f"http://{self.host}/ISAPI/Image/channels/{self.channel}"
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
            
            # Replace SharpnessLevel value
            xml_str = re.sub(
                r'<SharpnessLevel>.*?</SharpnessLevel>',
                f'<SharpnessLevel>{sharpness}</SharpnessLevel>',
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
            _LOGGER.error("Failed to set sharpness: %s", e)
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get device info (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get device info: %s", e)
            return {}

    def get_capabilities(self) -> dict:
        """Get device capabilities to detect NVR vs camera, multi-channel support."""
        try:
            xml = self._get("/ISAPI/System/capabilities")
            
            capabilities = {}
            
            # Analog cameras (for NVR/DVR)
            analog_inputs = xml.find(f".//{XML_NS}SysCap/{XML_NS}VideoCap/{XML_NS}videoInputPortNums")
            capabilities["analog_cameras_inputs"] = int(analog_inputs.text.strip()) if analog_inputs is not None and analog_inputs.text else 0
            
            # Digital cameras (for NVR)
            digital_inputs = xml.find(f".//{XML_NS}RacmCap/{XML_NS}inputProxyNums")
            capabilities["digital_cameras_inputs"] = int(digital_inputs.text.strip()) if digital_inputs is not None and digital_inputs.text else 0
            
            # IO ports
            io_inputs = xml.find(f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOInputPortNums")
            capabilities["input_ports"] = int(io_inputs.text.strip()) if io_inputs is not None and io_inputs.text else 0
            
            io_outputs = xml.find(f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOOutputPortNums")
            capabilities["output_ports"] = int(io_outputs.text.strip()) if io_outputs is not None and io_outputs.text else 0
            
            # Holiday mode support
            holiday_support = xml.find(f".//{XML_NS}SysCap/{XML_NS}isSupportHolidy")
            capabilities["support_holiday_mode"] = holiday_support.text.strip().lower() == "true" if holiday_support is not None and holiday_support.text else False
            
            # Determine if NVR (more than 1 camera input)
            capabilities["is_nvr"] = (capabilities["analog_cameras_inputs"] + capabilities["digital_cameras_inputs"]) > 1
            
            return capabilities
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get capabilities (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get capabilities: %s", e)
            return {"analog_cameras_inputs": 0, "digital_cameras_inputs": 0, "input_ports": 0, "output_ports": 0, "support_holiday_mode": False, "is_nvr": False}

    def get_cameras(self) -> list:
        """Discover all cameras/channels on the device."""
        cameras = []
        
        try:
            capabilities = self.get_capabilities()
            
            if not capabilities.get("is_nvr", False):
                # Single IP camera - check for multiple streaming channels
                try:
                    xml = self._get("/ISAPI/Streaming/channels")
                    streaming_channels = xml.findall(f".//{XML_NS}StreamingChannel")
                    
                    channel_ids = set()
                    for channel in streaming_channels:
                        video_elem = channel.find(f".//{XML_NS}Video")
                        if video_elem is not None:
                            channel_id_elem = video_elem.find(f".//{XML_NS}videoInputChannelID")
                            if channel_id_elem is not None and channel_id_elem.text:
                                channel_ids.add(int(channel_id_elem.text.strip()))
                    
                    # If no channels found, default to channel 1
                    if not channel_ids:
                        channel_ids = {1}
                    
                    device_name = self.device_info.get("deviceName", self.host)
                    is_multi_channel = len(channel_ids) > 1
                    
                    for channel_id in sorted(channel_ids):
                        camera_name = f"{device_name} - Channel {channel_id}" if is_multi_channel else device_name
                        cameras.append({
                            "id": channel_id,
                            "name": camera_name,
                            "model": self.device_info.get("model", ""),
                            "serial_no": self.device_info.get("serialNumber", ""),
                            "firmware": self.device_info.get("firmwareVersion", ""),
                            "input_port": channel_id,
                            "connection_type": "direct",
                        })
                except Exception as e:
                    _LOGGER.warning("Failed to get streaming channels, using default channel 1: %s", e)
                    # Fallback to single channel
                    device_name = self.device_info.get("deviceName", self.host)
                    cameras.append({
                        "id": 1,
                        "name": device_name,
                        "model": self.device_info.get("model", ""),
                        "serial_no": self.device_info.get("serialNumber", ""),
                        "firmware": self.device_info.get("firmwareVersion", ""),
                        "input_port": 1,
                        "connection_type": "direct",
                    })
            else:
                # NVR - get digital cameras
                if capabilities.get("digital_cameras_inputs", 0) > 0:
                    try:
                        xml = self._get("/ISAPI/ContentMgmt/InputProxy/channels")
                        digital_cameras = xml.findall(f".//{XML_NS}InputProxyChannel")
                        
                        for camera_elem in digital_cameras:
                            camera_id_elem = camera_elem.find(f".//{XML_NS}id")
                            if camera_id_elem is None or not camera_id_elem.text:
                                continue
                            
                            camera_id = int(camera_id_elem.text.strip())
                            source = camera_elem.find(f".//{XML_NS}sourceInputPortDescriptor")
                            
                            if source is None:
                                continue
                            
                            name_elem = camera_elem.find(f".//{XML_NS}name")
                            model_elem = source.find(f".//{XML_NS}model")
                            serial_elem = source.find(f".//{XML_NS}serialNumber")
                            firmware_elem = source.find(f".//{XML_NS}firmwareVersion")
                            input_port_elem = source.find(f".//{XML_NS}srcInputPort")
                            
                            serial_no = serial_elem.text.strip() if serial_elem is not None and serial_elem.text else f"{self.device_info.get('serialNumber', '')}_{camera_id}"
                            
                            cameras.append({
                                "id": camera_id,
                                "name": name_elem.text.strip() if name_elem is not None and name_elem.text else f"Camera {camera_id}",
                                "model": model_elem.text.strip() if model_elem is not None and model_elem.text else "Unknown",
                                "serial_no": serial_no,
                                "firmware": firmware_elem.text.strip() if firmware_elem is not None and firmware_elem.text else "",
                                "input_port": int(input_port_elem.text.strip()) if input_port_elem is not None and input_port_elem.text else camera_id,
                                "connection_type": "proxied",
                            })
                    except Exception as e:
                        _LOGGER.warning("Failed to get digital cameras: %s", e)
                
                # NVR - get analog cameras
                if capabilities.get("analog_cameras_inputs", 0) > 0:
                    try:
                        xml = self._get("/ISAPI/System/Video/inputs/channels")
                        analog_cameras = xml.findall(f".//{XML_NS}VideoInputChannel")
                        
                        for camera_elem in analog_cameras:
                            camera_id_elem = camera_elem.find(f".//{XML_NS}id")
                            if camera_id_elem is None or not camera_id_elem.text:
                                continue
                            
                            camera_id = int(camera_id_elem.text.strip())
                            name_elem = camera_elem.find(f".//{XML_NS}name")
                            model_elem = camera_elem.find(f".//{XML_NS}resDesc")
                            input_port_elem = camera_elem.find(f".//{XML_NS}inputPort")
                            
                            serial_no = f"{self.device_info.get('serialNumber', '')}-VI{camera_id}"
                            
                            cameras.append({
                                "id": camera_id,
                                "name": name_elem.text.strip() if name_elem is not None and name_elem.text else f"Analog Camera {camera_id}",
                                "model": model_elem.text.strip() if model_elem is not None and model_elem.text else "Unknown",
                                "serial_no": serial_no,
                                "firmware": "",
                                "input_port": int(input_port_elem.text.strip()) if input_port_elem is not None and input_port_elem.text else camera_id,
                                "connection_type": "direct",
                            })
                    except Exception as e:
                        _LOGGER.warning("Failed to get analog cameras: %s", e)
            
            return cameras
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get cameras (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get cameras: %s", e)
            # Fallback to single channel
            return [{
                "id": 1,
                "name": self.device_info.get("deviceName", self.host),
                "model": self.device_info.get("model", ""),
                "serial_no": self.device_info.get("serialNumber", ""),
                "firmware": self.device_info.get("firmwareVersion", ""),
                "input_port": 1,
                "connection_type": "direct",
            }]

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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get two-way audio (camera may be restarting): %s", e)
            else:
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
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response:
                error_msg = _extract_error_message(e.response)
                if error_msg:
                    _LOGGER.error("Failed to open audio session: %s", error_msg)
                else:
                    _LOGGER.error("Failed to open audio session: %s %s", e.response.status_code, e.response.reason)
            else:
                _LOGGER.error("Failed to open audio session: %s", e)
            return None
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
        """Play a 3-second test tone: 1000 Hz for most of it, then ramp to 2500 Hz at end.
        
        ⚠️ STATUS: THIS TEST TONE SORTA WORKS (partially functional) ⚠️
        
        NOTE FOR DEVELOPERS: This test tone function is partially working but may have issues.
        If you have experience with Hikvision ISAPI audio streaming or G.711 codec implementation,
        your help would be greatly appreciated to improve this!
        
        HOW IT CURRENTLY WORKS (AI-generated, not 100% certain):
        - Generates a sine wave test tone programmatically (1000 Hz, ramping to 2500 Hz)
        - Converts PCM samples to G.711ulaw format using a custom linear_to_ulaw function
        - Sends the audio data to /ISAPI/System/TwoWayAudio/channels/1/audioData
        - The tone is 3 seconds at 8kHz sample rate (24,000 samples total)
        - This appears to work to some degree, but may not be perfect
        
        KNOWN ISSUES / UNCERTAINTIES:
        - The G.711ulaw conversion might have bugs (custom implementation, not using standard library)
        - Audio might need to be sent in chunks rather than all at once
        - Session management might be incorrect (open/close timing)
        - The endpoint might require different headers or data format
        - Quality or reliability may be poor
        
        If you can help improve this, please check:
        - Hikvision ISAPI documentation for two-way audio streaming
        - Standard G.711ulaw encoding libraries (pyaudio, wave, etc.)
        - Compare with working audio streaming implementations
        Any contributions welcome!
        """
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
            
            # Step 4: Generate 3-second test tone
            _LOGGER.info("Generating 3-second test tone...")
            sample_rate = 8000
            duration = 3.0
            num_samples = int(sample_rate * duration)
            
            # Tone parameters:
            # - 1000 Hz for first ~2.5 seconds
            # - Ramp from 1000 to 2500 Hz over ~0.3 seconds (at 2.5s mark)
            # - Hold at 2500 Hz for ~0.2 seconds (end)
            base_freq = 1000  # Hz
            end_freq = 2500  # Hz
            ramp_start_time = 2.5  # Start ramping at 2.5 seconds
            ramp_duration = 0.3  # Ramp over 0.3 seconds
            hold_end_time = 3.0  # Hold until end
            
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
                
                # Determine frequency based on time
                if t < ramp_start_time:
                    # Hold at 1000 Hz
                    freq = base_freq
                elif t < ramp_start_time + ramp_duration:
                    # Ramp from 1000 to 2500 Hz
                    ramp_progress = (t - ramp_start_time) / ramp_duration
                    freq = base_freq + (end_freq - base_freq) * ramp_progress
                else:
                    # Hold at 2500 Hz until end
                    freq = end_freq
                
                # Generate sine wave at current frequency
                sample = math.sin(2 * math.pi * freq * t)
                pcm_sample = int(sample * 32767)
                ulaw_byte = linear_to_ulaw(pcm_sample)
                ulaw_data.append(ulaw_byte)
            
            _LOGGER.info("Generated %d bytes of audio", len(ulaw_data))
            
            # Step 5: Send all audio in one request
            _LOGGER.info("Sending audio data to camera...")
            
            # According to ISAPI PDF: sessionId is a query parameter (required for multi-channel, optional for single channel)
            endpoint = f"http://{self.host}/ISAPI/System/TwoWayAudio/channels/1/audioData?sessionId={session_id}"
            response = requests.put(
                endpoint,
                auth=(self.username, self.password),
                data=bytes(ulaw_data),
                headers={"Content-Type": "application/octet-stream"},
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
            if enabled is not None and enabled.text:
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get motion detection (camera may be restarting): %s", e)
            else:
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
            if enabled is not None and enabled.text:
                result["enabled"] = enabled.text.strip().lower() == "true"
            
            return result
        except AuthenticationError:
            raise
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get tamper detection (camera may be restarting): %s", e)
            else:
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

    def get_snapshot(self, channel: int = None, stream_id: int = None) -> Optional[bytes]:
        """Get camera snapshot image."""
        try:
            if stream_id is not None:
                # Use specific stream ID (e.g., 101, 102, 103, 104)
                snapshot_channel = stream_id
            else:
                # Snapshot channel format: 10X where X is channel number (101 = channel 1, 102 = channel 2, etc.)
                snapshot_channel = 100 + (channel if channel is not None else self.channel)
            url = f"http://{self.host}/ISAPI/Streaming/channels/{snapshot_channel}/picture"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors with more context
            error_msg = _extract_error_message(e.response) if hasattr(e, 'response') and e.response else ""
            if e.response.status_code == 503:
                if error_msg:
                    _LOGGER.debug("Failed to get snapshot: Service Unavailable (503) - %s", error_msg)
                else:
                    _LOGGER.debug("Failed to get snapshot: Service Unavailable (503) - camera may be busy with another operation (e.g., two-way audio, streaming, or processing)")
            elif e.response.status_code == 401:
                if error_msg:
                    _LOGGER.error("Failed to get snapshot: Authentication failed (401) - %s", error_msg)
                else:
                    _LOGGER.error("Failed to get snapshot: Authentication failed (401) - check username and password")
            elif e.response.status_code == 403:
                if error_msg:
                    _LOGGER.debug("Failed to get snapshot: Access forbidden (403) - %s", error_msg)
                else:
                    _LOGGER.debug("Failed to get snapshot: Access forbidden (403) - user may not have required permissions")
            else:
                if error_msg:
                    _LOGGER.warning("Failed to get snapshot: HTTP %d - %s", e.response.status_code, error_msg)
                else:
                    _LOGGER.warning("Failed to get snapshot: HTTP %d - %s", e.response.status_code, e)
            return None
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get snapshot (camera may be restarting): %s", e)
            else:
                _LOGGER.warning("Failed to get snapshot: %s", e)
            return None

    def get_camera_streams(self, channel_id: int) -> list[dict]:
        """Get available streams for a camera channel."""
        from .const import STREAM_TYPE
        streams = []
        
        for stream_type_id, stream_type_name in STREAM_TYPE.items():
            # Stream ID format: {channel_id}0{stream_type_id} (e.g., 101, 102, 103, 104)
            stream_id = channel_id * 100 + stream_type_id
            try:
                xml = self._get(f"/ISAPI/Streaming/channels/{stream_id}")
                
                # Check if root is StreamingChannel or if it's nested
                stream_channel = None
                if xml.tag.endswith("StreamingChannel"):
                    stream_channel = xml
                else:
                    # Check for error response first
                    status_code_elem = xml.find(f".//{XML_NS}ResponseStatus/{XML_NS}statusCode")
                    if status_code_elem is not None:
                        status = int(status_code_elem.text.strip())
                        if status != 1:  # 1 = success
                            _LOGGER.debug("Stream %s (ID %d) returned error status %d", stream_type_name, stream_id, status)
                            continue
                    
                    # Check if StreamingChannel exists as child
                    stream_channel = xml.find(f".//{XML_NS}StreamingChannel")
                
                if stream_channel is None:
                    _LOGGER.debug("Stream %s (ID %d) - no StreamingChannel found, root tag: %s", 
                                 stream_type_name, stream_id, xml.tag)
                    continue
                
                # Parse stream info
                enabled_elem = stream_channel.find(f".//{XML_NS}enabled")
                enabled = enabled_elem is not None and enabled_elem.text.strip().lower() == "true"
                
                # Get video info
                video_elem = stream_channel.find(f".//{XML_NS}Video")
                codec = None
                width = 0
                height = 0
                if video_elem is not None:
                    codec_elem = video_elem.find(f".//{XML_NS}videoCodecType")
                    if codec_elem is not None:
                        codec = codec_elem.text.strip()
                    width_elem = video_elem.find(f".//{XML_NS}videoResolutionWidth")
                    if width_elem is not None:
                        width = int(width_elem.text.strip())
                    height_elem = video_elem.find(f".//{XML_NS}videoResolutionHeight")
                    if height_elem is not None:
                        height = int(height_elem.text.strip())
                
                # Get audio info
                audio_elem = stream_channel.find(f".//{XML_NS}Audio")
                audio = False
                if audio_elem is not None:
                    audio_enabled = audio_elem.find(f".//{XML_NS}enabled")
                    if audio_enabled is not None:
                        audio = audio_enabled.text.strip().lower() == "true"
                
                streams.append({
                    "id": stream_id,
                    "type_id": stream_type_id,
                    "type": stream_type_name,
                    "enabled": enabled,
                    "codec": codec,
                    "width": width,
                    "height": height,
                    "audio": audio,
                })
                _LOGGER.debug("Found stream %s (ID %d) for channel %d", stream_type_name, stream_id, channel_id)
            except Exception as e:
                # Stream type not available for this camera, skip it
                _LOGGER.debug("Stream type %s (ID %d) not available for channel %d: %s", 
                             stream_type_name, stream_type_id, channel_id, str(e))
                continue
        
        _LOGGER.info("Found %d stream(s) for camera channel %d: %s", 
                    len(streams), channel_id, [s["type"] for s in streams] if streams else "none")
        return streams

    def get_rtsp_port(self) -> int:
        """Get RTSP port from device."""
        try:
            xml = self._get("/ISAPI/Security/adminAccesses")
            protocols = xml.findall(f".//{XML_NS}AdminAccessProtocol")
            
            for protocol in protocols:
                protocol_type = protocol.find(f".//{XML_NS}protocol")
                port_elem = protocol.find(f".//{XML_NS}portNo")
                
                if protocol_type is not None and protocol_type.text.strip().upper() == "RTSP":
                    if port_elem is not None and port_elem.text:
                        return int(port_elem.text.strip())
            
            # Default RTSP port
            return 554
        except Exception as e:
            _LOGGER.debug("Failed to get RTSP port, using default 554: %s", e)
            return 554

    def get_stream_source(self, stream_id: int) -> str:
        """Get RTSP stream source URL."""
        from urllib.parse import quote
        rtsp_port = self.get_rtsp_port()
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        return f"rtsp://{username}:{password}@{self.host}:{rtsp_port}/Streaming/channels/{stream_id}"

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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get streaming status (camera may be restarting): %s", e)
            else:
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
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get system status (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get system status: %s", e)
            return {}

    def get_field_detection(self) -> dict:
        """Get field detection (intrusion) settings."""
        try:
            xml = self._get(f"/ISAPI/Smart/FieldDetection/{self.channel}")
            result = {}
            # Find enabled directly like tamper detection does
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None and enabled.text:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            else:
                _LOGGER.warning("FieldDetection enabled element not found. Root tag: %s, XML: %s", xml.tag, ET.tostring(xml, encoding='unicode')[:500])
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get field detection (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get field detection: %s", e)
            return {}

    def set_field_detection(self, enabled: bool) -> bool:
        """Enable/disable field detection (intrusion)."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/FieldDetection/{self.channel}"
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
            xml = self._get(f"/ISAPI/Smart/LineDetection/{self.channel}")
            result = {}
            # Find enabled directly - try multiple methods to handle namespace variations
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is None:
                # Fallback: XML might not have namespace declaration
                enabled = xml.find(".//enabled")
            if enabled is None:
                # Fallback: Try as direct child of root
                for child in xml:
                    if child.tag.endswith("enabled") or child.tag == "enabled":
                        enabled = child
                        break
            if enabled is not None and enabled.text:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            else:
                _LOGGER.warning("LineDetection enabled element not found. Root tag: %s, XML: %s", xml.tag, ET.tostring(xml, encoding='unicode')[:500])
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get line detection (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get line detection: %s", e)
            return {}

    def set_line_detection(self, enabled: bool) -> bool:
        """Enable/disable line detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/LineDetection/{self.channel}"
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
            xml = self._get(f"/ISAPI/Smart/SceneChangeDetection/{self.channel}")
            result = {}
            # Find enabled directly like field_detection and line_detection do
            # The root element is SceneChangeDetection, so enabled is a direct child
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None and enabled.text:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            else:
                _LOGGER.warning("SceneChangeDetection enabled element not found. Root tag: %s, XML: %s", xml.tag, ET.tostring(xml, encoding='unicode')[:500])
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get scene change detection (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get scene change detection: %s", e)
            return {}

    def set_scene_change_detection(self, enabled: bool) -> bool:
        """Enable/disable scene change detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/SceneChangeDetection/{self.channel}"
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
            xml = self._get(f"/ISAPI/Smart/regionEntrance/{self.channel}")
            result = {}
            # Find enabled directly like tamper detection does
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None and enabled.text:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            else:
                _LOGGER.warning("RegionEntrance enabled element not found. Root tag: %s, XML: %s", xml.tag, ET.tostring(xml, encoding='unicode')[:500])
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get region entrance (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get region entrance: %s", e)
            return {}

    def set_region_entrance(self, enabled: bool) -> bool:
        """Enable/disable region entrance detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/regionEntrance/{self.channel}"
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
            xml = self._get(f"/ISAPI/Smart/regionExiting/{self.channel}")
            result = {}
            # Find enabled directly like tamper detection does
            enabled = xml.find(f".//{XML_NS}enabled")
            if enabled is not None and enabled.text:
                    result["enabled"] = enabled.text.strip().lower() == "true"
            else:
                _LOGGER.warning("RegionExiting enabled element not found. Root tag: %s, XML: %s", xml.tag, ET.tostring(xml, encoding='unicode')[:500])
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get region exiting (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get region exiting: %s", e)
            return {}

    def set_region_exiting(self, enabled: bool) -> bool:
        """Enable/disable region exiting detection."""
        try:
            url = f"http://{self.host}/ISAPI/Smart/regionExiting/{self.channel}"
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

    def get_alarm_input(self, port_id: int = 1) -> dict:
        """Get alarm input port settings."""
        try:
            xml = self._get(f"/ISAPI/System/IO/inputs/{port_id}")
            result = {}
            port = xml.find(f".//{XML_NS}IOInputPort")
            if port is not None:
                enabled = port.find(f".//{XML_NS}enabled")
                if enabled is not None:
                    result["enabled"] = enabled.text.strip().lower() == "true"
                triggering = port.find(f".//{XML_NS}triggering")
                if triggering is not None:
                    result["triggering"] = triggering.text.strip()
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get alarm input (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get alarm input: %s", e)
            return {}

    def set_alarm_input(self, port_id: int = 1, enabled: bool = True) -> bool:
        """Enable/disable alarm input port."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/inputs/{port_id}"
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
            _LOGGER.error("Failed to set alarm input: %s", e)
            return False

    def get_alarm_output(self, port_id: int = 1) -> dict:
        """Get alarm output port status."""
        try:
            xml = self._get(f"/ISAPI/System/IO/outputs/{port_id}/status")
            result = {}
            port_status = xml.find(f".//{XML_NS}IOPortStatus")
            if port_status is not None:
                io_state = port_status.find(f".//{XML_NS}ioState")
                if io_state is not None:
                    # "active" means on, "inactive" means off
                    result["enabled"] = io_state.text.strip().lower() == "active"
            return result
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get alarm output (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get alarm output: %s", e)
            return {}

    def set_alarm_output(self, port_id: int = 1, enabled: bool = True) -> bool:
        """Trigger alarm output port (high/low)."""
        try:
            url = f"http://{self.host}/ISAPI/System/IO/outputs/{port_id}/trigger"
            output_state = "high" if enabled else "low"
            xml_data = f'<?xml version="1.0" encoding="UTF-8"?><IOPortData><outputState>{output_state}</outputState></IOPortData>'
            
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
            _LOGGER.error("Failed to set alarm output: %s", e)
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

    def _get_event_notification_host(self, xml_root):
        """Get the first HTTP notification host from XML."""
        hosts = xml_root.findall(f".//{XML_NS}HttpHostNotification")
        if hosts:
            return hosts[0]
        return None

    def set_alarm_server(self, base_url: str, path: str) -> str:
        """Set event notifications listener server."""
        import ipaddress
        from urllib.parse import urlparse
        
        try:
            # Get current notification hosts
            url = f"http://{self.host}/ISAPI/Event/notification/httpHosts"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            
            _LOGGER.debug("Received alarm server XML: %s", response.text)
            xml_root = ET.fromstring(response.text)
            host = self._get_event_notification_host(xml_root)
            
            if host is None:
                _LOGGER.warning("No HTTP notification host found")
                return ""
            
            address = urlparse(base_url)
            
            # Check if already configured correctly - search direct children
            old_protocol = host.find(f"{XML_NS}protocolType")
            old_url = host.find(f"{XML_NS}url")
            old_port = host.find(f"{XML_NS}portNo")
            addressing_type = host.find(f"{XML_NS}addressingFormatType")
            old_address = None
            
            if addressing_type is not None and addressing_type.text == "ipaddress":
                old_address_elem = host.find(f"{XML_NS}ipAddress")
                if old_address_elem is not None and old_address_elem.text:
                    old_address = old_address_elem.text
            else:
                old_address_elem = host.find(f"{XML_NS}hostName")
                if old_address_elem is not None and old_address_elem.text:
                    old_address = old_address_elem.text
            
            port = address.port or (443 if address.scheme == "https" else 80)
            if (old_protocol is not None and old_protocol.text and old_protocol.text == address.scheme.upper() and
                old_address == address.hostname and
                old_port is not None and old_port.text and old_port.text == str(port) and
                old_url is not None and old_url.text and old_url.text == path):
                _LOGGER.debug("Notification host already configured correctly")
                return path
            
            # Check if already configured to the same path
            if old_url is not None and old_url.text and old_url.text == "/api/hikvision" and path == "/api/hikvision":
                _LOGGER.debug("Notification host already set to /api/hikvision")
            
            # Warn if configured for another path (but not if it's just "/" which is default/unset)
            if old_url is not None and old_url.text and old_url.text != path and old_url.text != "/":
                _LOGGER.info(
                    "Notification host is currently set to '%s'. Updating to '%s'.",
                    old_url.text, path
                )
            elif old_url is not None and old_url.text == "/":
                _LOGGER.info("Notification host is unset (default '/'). Configuring to '%s'.", path)
            
            # Update URL
            if old_url is not None:
                old_url.text = path
            else:
                url_elem = ET.SubElement(host, f"{XML_NS}url")
                url_elem.text = path
            
            # Update protocol
            if old_protocol is not None:
                old_protocol.text = address.scheme.upper()
            else:
                protocol_elem = ET.SubElement(host, f"{XML_NS}protocolType")
                protocol_elem.text = address.scheme.upper()
            
            # Set parameter format
            param_format = host.find(f"{XML_NS}parameterFormatType")
            if param_format is not None:
                param_format.text = "XML"
            else:
                param_format_elem = ET.SubElement(host, f"{XML_NS}parameterFormatType")
                param_format_elem.text = "XML"
            
            # Set address type and value
            try:
                ipaddress.ip_address(address.hostname)
                # IP address
                if addressing_type is not None:
                    addressing_type.text = "ipaddress"
                else:
                    addressing_type_elem = ET.SubElement(host, f"{XML_NS}addressingFormatType")
                    addressing_type_elem.text = "ipaddress"
                
                ip_elem = host.find(f"{XML_NS}ipAddress")
                if ip_elem is not None:
                    ip_elem.text = address.hostname
                else:
                    ip_elem = ET.SubElement(host, f"{XML_NS}ipAddress")
                    ip_elem.text = address.hostname
                
                # Remove hostname if exists
                hostname_elem = host.find(f"{XML_NS}hostName")
                if hostname_elem is not None:
                    host.remove(hostname_elem)
            except ValueError:
                # Hostname
                if addressing_type is not None:
                    addressing_type.text = "hostname"
                else:
                    addressing_type_elem = ET.SubElement(host, f"{XML_NS}addressingFormatType")
                    addressing_type_elem.text = "hostname"
                
                hostname_elem = host.find(f"{XML_NS}hostName")
                if hostname_elem is not None:
                    hostname_elem.text = address.hostname
                else:
                    hostname_elem = ET.SubElement(host, f"{XML_NS}hostName")
                    hostname_elem.text = address.hostname
                
                # Remove IP if exists
                ip_elem = host.find(f"{XML_NS}ipAddress")
                if ip_elem is not None:
                    host.remove(ip_elem)
            
            # Set port
            if old_port is not None:
                old_port.text = str(port)
            else:
                port_elem = ET.SubElement(host, f"{XML_NS}portNo")
                port_elem.text = str(port)
            
            # Set authentication method
            auth_method = host.find(f"{XML_NS}httpAuthenticationMethod")
            if auth_method is not None:
                auth_method.text = "none"
            else:
                auth_elem = ET.SubElement(host, f"{XML_NS}httpAuthenticationMethod")
                auth_elem.text = "none"
            
            # Send updated XML - preserve XML declaration and namespace
            # Register namespace to avoid ns0 prefixes
            ET.register_namespace('', 'http://www.hikvision.com/ver20/XMLSchema')
            xml_str = ET.tostring(xml_root, encoding='unicode', xml_declaration=True)
            _LOGGER.debug("Sending alarm server XML: %s", xml_str)
            response = requests.put(
                url,
                auth=(self.username, self.password),
                data=xml_str,
                headers={"Content-Type": "application/xml"},
                verify=False,
                timeout=5
            )
            if response.status_code == 400:
                _LOGGER.error("Bad request - XML sent: %s", xml_str)
                _LOGGER.error("Response: %s", response.text)
            response.raise_for_status()
            _LOGGER.info("Successfully configured notification host: %s%s", base_url, path)
            return path
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                _LOGGER.error("Failed to set alarm server: %s - Response: %s", e, e.response.text)
            else:
                _LOGGER.error("Failed to set alarm server: %s", e)
            return ""
        except Exception as e:
            _LOGGER.error("Failed to set alarm server: %s", e)
            return ""

    def get_alarm_server(self) -> dict:
        """Get current notification host configuration."""
        try:
            url = f"http://{self.host}/ISAPI/Event/notification/httpHosts"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            response.raise_for_status()
            
            xml_root = ET.fromstring(response.text)
            host = self._get_event_notification_host(xml_root)
            
            if host is None:
                return {
                    "host": None,
                    "path": None,
                    "port": None,
                    "protocol": None
                }
            
            # Get protocol
            protocol_elem = host.find(f"{XML_NS}protocolType")
            protocol = protocol_elem.text if protocol_elem is not None and protocol_elem.text else None
            
            # Get URL path
            url_elem = host.find(f"{XML_NS}url")
            path = url_elem.text if url_elem is not None and url_elem.text else None
            
            # Get port
            port_elem = host.find(f"{XML_NS}portNo")
            port = port_elem.text if port_elem is not None and port_elem.text else None
            
            # Get host (IP or hostname)
            addressing_type = host.find(f"{XML_NS}addressingFormatType")
            host_address = None
            if addressing_type is not None and addressing_type.text == "ipaddress":
                ip_elem = host.find(f"{XML_NS}ipAddress")
                if ip_elem is not None and ip_elem.text:
                    host_address = ip_elem.text
            else:
                hostname_elem = host.find(f"{XML_NS}hostName")
                if hostname_elem is not None and hostname_elem.text:
                    host_address = hostname_elem.text
            
            return {
                "host": host_address,
                "path": path,
                "port": int(port) if port else None,
                "protocol": protocol
            }
        except Exception as e:
            # Connection errors are expected during camera restarts - log as debug
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get alarm server (camera may be restarting): %s", e)
            else:
                _LOGGER.error("Failed to get alarm server: %s", e)
            return {
                "host": None,
                "path": None,
                "port": None,
                "protocol": None
            }

    def get_supported_events(self):
        """Get list of all supported events from Event/triggers API."""
        from .models import EventInfo
        from .const import EVENTS, EVENTS_ALTERNATE_ID, EVENT_IO
        
        events = []
        
        try:
            xml = self._get("/ISAPI/Event/triggers")
            
            # Debug: Log root element and first 500 chars of XML
            _LOGGER.debug("Event/triggers root tag: %s, root attrib: %s", xml.tag, xml.attrib)
            import xml.etree.ElementTree as ET
            xml_str = ET.tostring(xml, encoding='unicode')[:500]
            _LOGGER.debug("Event/triggers XML (first 500 chars): %s", xml_str)
            
            # Find EventNotification/EventTriggerList/EventTrigger or EventTriggerList/EventTrigger
            event_notification = xml.find(f".//{XML_NS}EventNotification")
            if event_notification is not None:
                event_trigger_list = event_notification.find(f".//{XML_NS}EventTriggerList")
            else:
                event_trigger_list = xml.find(f".//{XML_NS}EventTriggerList")
            
            # Also check if root itself is EventTriggerList (some cameras might return it directly)
            if event_trigger_list is None and xml.tag.endswith("EventTriggerList"):
                event_trigger_list = xml
            
            if event_trigger_list is None:
                _LOGGER.warning("No EventTriggerList found in Event/triggers response. Root tag: %s", xml.tag)
                # Log all child elements for debugging
                all_tags = [child.tag for child in xml]
                _LOGGER.debug("Available XML elements: %s", all_tags[:10])
                return events
            
            event_triggers = event_trigger_list.findall(f".//{XML_NS}EventTrigger")
            
            for event_trigger in event_triggers:
                # Get eventType
                event_type_elem = event_trigger.find(f".//{XML_NS}eventType")
                if event_type_elem is None or not event_type_elem.text:
                    continue
                
                event_id = event_type_elem.text.strip().lower()
                
                # Handle alternate event type mapping
                if event_id in EVENTS_ALTERNATE_ID:
                    event_id = EVENTS_ALTERNATE_ID[event_id]
                
                # Skip if not in our supported events
                if event_id not in EVENTS:
                    continue
                
                # Get channel_id and io_port_id
                channel_id = 0
                io_port_id = 0
                
                if event_id == EVENT_IO:
                    # I/O events use inputIOPortID
                    io_port_elem = event_trigger.find(f".//{XML_NS}inputIOPortID")
                    if io_port_elem is None or not io_port_elem.text:
                        io_port_elem = event_trigger.find(f".//{XML_NS}dynInputIOPortID")
                    if io_port_elem is not None and io_port_elem.text:
                        io_port_id = int(io_port_elem.text.strip())
                else:
                    # Other events use videoInputChannelID
                    channel_elem = event_trigger.find(f".//{XML_NS}videoInputChannelID")
                    if channel_elem is None or not channel_elem.text:
                        channel_elem = event_trigger.find(f".//{XML_NS}dynVideoInputChannelID")
                    if channel_elem is not None and channel_elem.text:
                        channel_id = int(channel_elem.text.strip())
                
                # Get notification methods to determine if event is disabled
                notification_list = event_trigger.find(f".//{XML_NS}EventTriggerNotificationList")
                notifications = []
                disabled = False
                if notification_list is not None:
                    notification_elems = notification_list.findall(f".//{XML_NS}EventTriggerNotification")
                    for notif in notification_elems:
                        method_elem = notif.find(f".//{XML_NS}notificationMethod")
                        if method_elem is not None and method_elem.text:
                            notifications.append(method_elem.text.strip())
                    # Event is disabled if "center" (Surveillance Center) is not in notifications
                    disabled = "center" not in notifications
                
                events.append(EventInfo(
                    id=event_id,
                    channel_id=channel_id,
                    io_port_id=io_port_id,
                    disabled=disabled,
                ))
            
            _LOGGER.info("Found %d supported events from Event/triggers", len(events))
            return events
            
        except Exception as e:
            _LOGGER.warning("Failed to get supported events from Event/triggers: %s", e)
            return events

    def get_audio_alarm(self) -> Optional[dict]:
        """Get audio alarm configuration."""
        try:
            url = f"http://{self.host}/ISAPI/Event/triggers/notifications/AudioAlarm?format=json"
            response = requests.get(
                url,
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                _LOGGER.debug("Audio alarm endpoint not accessible (403) - may require permissions")
                return None
            elif response.status_code == 404:
                _LOGGER.debug("Audio alarm endpoint not found (404) - feature may not be supported")
                return None
            response.raise_for_status()
            return json.loads(response.text)
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.debug("Failed to get audio alarm (camera may be restarting): %s", e)
            elif isinstance(e, AuthenticationError):
                raise
            else:
                _LOGGER.debug("Failed to get audio alarm: %s", e)
            return None

    def set_audio_alarm(self, audio_class: Optional[str] = None, alert_audio_id: Optional[int] = None,
                        audio_volume: Optional[int] = None, alarm_times: Optional[int] = None) -> bool:
        """Set audio alarm configuration."""
        try:
            # Get current config first
            current = self.get_audio_alarm()
            if not current or "AudioAlarm" not in current:
                _LOGGER.error("Cannot set audio alarm - failed to get current configuration")
                return False

            audio_alarm = current["AudioAlarm"].copy()

            # Update only provided values
            if audio_class is not None:
                audio_alarm["audioClass"] = audio_class
            if alert_audio_id is not None:
                audio_alarm["alertAudioID"] = alert_audio_id
                # If setting alertAudioID, ensure audioClass is "alertAudio" (required for alertAudioID to work)
                if audio_class != "alertAudio" and audio_alarm.get("audioClass") != "alertAudio":
                    audio_alarm["audioClass"] = "alertAudio"
                # Also update audioID when using alertAudio
                audio_alarm["audioID"] = alert_audio_id
            if audio_volume is not None:
                audio_alarm["audioVolume"] = audio_volume
            if alarm_times is not None:
                audio_alarm["alarmTimes"] = alarm_times

            # PUT updated config
            url = f"http://{self.host}/ISAPI/Event/triggers/notifications/AudioAlarm?format=json"
            response = requests.put(
                url,
                json={"AudioAlarm": audio_alarm},
                auth=(self.username, self.password),
                verify=False,
                timeout=5
            )
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed - check username and password (401)")
            elif response.status_code == 403:
                _LOGGER.error("Access forbidden - user '%s' may not have required permissions (403)", self.username)
                return False
            response.raise_for_status()
            return True
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.error("Failed to set audio alarm (camera may be restarting): %s", e)
            elif isinstance(e, AuthenticationError):
                raise
            else:
                _LOGGER.error("Failed to set audio alarm: %s", e)
            return False

    def test_audio_alarm(self) -> bool:
        """Test/trigger audio alarm playback."""
        try:
            # Get current audio alarm config to get the audioID
            current = self.get_audio_alarm()
            if not current or "AudioAlarm" not in current:
                _LOGGER.debug("Cannot test audio alarm - failed to get current configuration")
                return False
            
            audio_alarm = current["AudioAlarm"]
            # Use audioID if available, otherwise use alertAudioID
            audio_id = audio_alarm.get("audioID") or audio_alarm.get("alertAudioID")
            if not audio_id:
                _LOGGER.debug("Cannot test audio alarm - no audioID found in configuration")
                return False
            
            # The test endpoint requires the audioID in the path: /AudioAlarm/{audioID}/test
            url = f"http://{self.host}/ISAPI/Event/triggers/notifications/AudioAlarm/{audio_id}/test?format=json"
            response = requests.put(
                url,
                json={},
                auth=(self.username, self.password),
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                return True
            else:
                error_msg = _extract_error_message(response)
                if response.status_code == 403:
                    if error_msg:
                        _LOGGER.debug("Audio alarm test endpoint not accessible (403): %s", error_msg)
                    else:
                        _LOGGER.debug("Audio alarm test endpoint not accessible (403)")
                elif response.status_code == 404:
                    _LOGGER.debug("Audio alarm test endpoint not found (404)")
                else:
                    if error_msg:
                        _LOGGER.debug("Audio alarm test returned status %d: %s", response.status_code, error_msg)
                    else:
                        _LOGGER.debug("Audio alarm test returned status %d", response.status_code)
            
            return False
        except Exception as e:
            if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                _LOGGER.warning("Failed to test audio alarm (timeout): %s", e)
            else:
                _LOGGER.debug("Failed to test audio alarm: %s", e)
            return False
