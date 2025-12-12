"""Events listener for Hikvision ISAPI event notifications."""
from __future__ import annotations

from http import HTTPStatus
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from aiohttp import web
from requests_toolbelt.multipart import MultipartDecoder

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONTENT_TYPE_TEXT_PLAIN, STATE_ON, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import slugify

from .const import ALARM_SERVER_PATH, DOMAIN, HIKVISION_EVENT, EVENTS_ALTERNATE_ID, EVENT_IO
from .models import AlertInfo

_LOGGER = logging.getLogger(__name__)

CONTENT_TYPE = "Content-Type"
CONTENT_TYPE_XML = (
    "application/xml",
    'application/xml; charset="UTF-8"',
    "text/xml",
)
CONTENT_TYPE_TEXT_HTML = "text/html"
CONTENT_TYPE_IMAGE = "image/jpeg"


class EventNotificationsView(HomeAssistantView):
    """Event notifications listener for Hikvision cameras."""

    def __init__(self, hass: HomeAssistant):
        """Initialize."""
        self.requires_auth = False
        self.url = ALARM_SERVER_PATH
        self.name = DOMAIN
        self.hass = hass

    async def post(self, request: web.Request):
        """Accept the POST request from camera."""
        _LOGGER.info("=== WEBHOOK RECEIVED === Source: %s, Headers: %s", request.remote, dict(request.headers))

        try:
            _LOGGER.info("--- Incoming event notification from %s ---", request.remote)
            xml = await self.parse_event_request(request)
            _LOGGER.info("Received XML (first 500 chars): %s", xml[:500] if xml else "None")
            _LOGGER.debug("Full XML: %s", xml)
            alert = self.parse_event_notification(xml)
            _LOGGER.info("Parsed alert: event=%s, channel=%s, io_port=%s", alert.event_id, alert.channel_id, alert.io_port_id)
            device_entry = self.get_isapi_device(request.remote, alert)
            _LOGGER.info("Found device entry: %s", device_entry.entry_id)
            self.update_alert_channel(device_entry, alert)
            self.trigger_sensor(device_entry, alert)
        except Exception as ex:  # pylint: disable=broad-except
            # Log duration parsing failures at debug level to reduce noise
            # These are expected when DurationList exists but relationEvent is missing
            if "Cannot extract event type from DurationList" in str(ex):
                _LOGGER.debug("Skipping duration event notification: %s", ex)
            else:
                _LOGGER.error("Cannot process incoming event: %s", ex, exc_info=True)

        response = web.Response(status=HTTPStatus.OK, content_type=CONTENT_TYPE_TEXT_PLAIN)
        return response

    def get_isapi_device(self, device_ip, alert: AlertInfo):
        """Get integration instance for device sending alert."""
        integration_entries = self.hass.config_entries.async_entries(DOMAIN)
        instance_identifiers = []
        entry = None
        
        if len(integration_entries) == 1:
            entry = integration_entries[0]
        else:
            # Search device by mac_address
            for item in integration_entries:
                if item.disabled_by:
                    continue

                device_info = self.hass.data[DOMAIN][item.entry_id].get("device_info", {})
                item_mac_address = device_info.get("macAddress", "").lower()
                instance_identifiers.append(item_mac_address)

                if item_mac_address and item_mac_address == alert.mac.lower():
                    entry = item
                    break

            # Search device by ip_address
            if not entry:
                for item in integration_entries:
                    if item.disabled_by:
                        continue

                    host = self.hass.data[DOMAIN][item.entry_id].get("host", "")
                    instance_identifiers.append(host)

                    if self.get_ip(urlparse(f"http://{host}").hostname or host) == device_ip:
                        entry = item
                        break

        if not entry:
            raise ValueError(f"Cannot find ISAPI instance for device {device_ip} in {instance_identifiers}")

        return entry

    def update_alert_channel(self, entry, alert: AlertInfo) -> None:
        """Fix channel id for NVR/DVR alert (channels > 32 are IP cameras)."""
        device_data = self.hass.data[DOMAIN][entry.entry_id]
        cameras = device_data.get("cameras", [])
        capabilities = device_data.get("capabilities", {})
        
        if alert.channel_id > 32 and capabilities.get("is_nvr", False):
            # Channel id above 32 is an IP camera on NVR/DVR
            # On DVRs that support analog cameras, 33 may not be camera 1 but camera 5 for example
            try:
                # Try to find camera by input_port (channel_id - 32)
                input_port = alert.channel_id - 32
                matching_camera = next(
                    (cam for cam in cameras if cam.get("input_port") == input_port),
                    None
                )
                if matching_camera:
                    alert.channel_id = matching_camera["id"]
                else:
                    # Fallback: just subtract 32
                    alert.channel_id = alert.channel_id - 32
            except (StopIteration, KeyError, TypeError):
                # Fallback: just subtract 32
                alert.channel_id = alert.channel_id - 32

    def get_ip(self, ip_string: str) -> str:
        """Return an IP if either hostname or IP is provided."""
        try:
            ipaddress.ip_address(ip_string)
            return ip_string
        except ValueError:
            resolved_hostname = socket.gethostbyname(ip_string)
            _LOGGER.debug("Resolve host %s resolves to IP %s", ip_string, resolved_hostname)
            return resolved_hostname

    async def parse_event_request(self, request: web.Request) -> str:
        """Extract XML content from multipart request or from simple request."""
        data = await request.read()
        content_type_header = request.headers.get(CONTENT_TYPE, "").strip()

        _LOGGER.debug("request headers: %s", request.headers)
        xml = None
        if content_type_header in CONTENT_TYPE_XML:
            xml = data.decode("utf-8")
        else:
            # "multipart/form-data; boundary=boundary"
            decoder = MultipartDecoder(data, content_type_header)
            for part in decoder.parts:
                headers = {}
                for key, value in part.headers.items():
                    assert isinstance(key, bytes)
                    headers[key.decode("ascii")] = value.decode("ascii")
                _LOGGER.debug("part headers: %s", headers)
                if headers.get(CONTENT_TYPE) in CONTENT_TYPE_XML:
                    xml = part.text
                if headers.get(CONTENT_TYPE) == CONTENT_TYPE_IMAGE:
                    _LOGGER.debug("image found")

        if not xml:
            raise ValueError(f"Unexpected event Content-Type {content_type_header}")
        return xml

    def parse_event_notification(self, xml: str) -> AlertInfo:
        """Parse incoming EventNotificationAlert XML message."""
        import xml.etree.ElementTree as ET
        
        # Fix for some cameras sending non html encoded data
        xml = xml.replace("&", "&amp;")
        
        try:
            root = ET.fromstring(xml)
            XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
            
            # Log the root tag and structure for debugging
            _LOGGER.info("Root tag: %s, Root attrib: %s", root.tag, root.attrib)
            
            # Try multiple ways to find EventNotificationAlert
            alert = None
            
            # Method 1: With namespace
            alert = root.find(f".//{XML_NS}EventNotificationAlert")
            
            # Method 2: Without namespace
            if alert is None:
                alert = root.find(".//EventNotificationAlert")
            
            # Method 3: Check if root itself is EventNotificationAlert (with or without namespace)
            if alert is None:
                if root.tag.endswith("EventNotificationAlert") or root.tag == "EventNotificationAlert":
                    alert = root
            
            # Method 4: Try finding by local name (strip namespace)
            if alert is None:
                for elem in root.iter():
                    local_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if local_name == "EventNotificationAlert":
                        alert = elem
                        _LOGGER.info("Found EventNotificationAlert by local name: %s", elem.tag)
                        break
            
            # If still not found, log the XML structure and all element tags
            if alert is None:
                _LOGGER.error("No EventNotificationAlert found. Root tag: %s", root.tag)
                _LOGGER.error("XML structure (first 1000 chars): %s", ET.tostring(root, encoding='unicode')[:1000])
                # Log all element tags found
                all_tags = [elem.tag for elem in root.iter()]
                _LOGGER.error("All XML tags found: %s", all_tags[:20])  # First 20 tags
                raise ValueError("No EventNotificationAlert found")
            
            # Try multiple methods to find eventType
            event_type_elem = None
            # Method 1: With namespace
            event_type_elem = alert.find(f".//{XML_NS}eventType")
            # Method 2: Without namespace
            if event_type_elem is None:
                event_type_elem = alert.find(".//eventType")
            # Method 3: Check for DurationList (version 2.0)
            if event_type_elem is None:
                duration = alert.find(f".//{XML_NS}DurationList/{XML_NS}Duration")
                if duration is not None:
                    event_type_elem = duration.find(f".//{XML_NS}relationEvent")
            # Method 4: Try without namespace in DurationList
            if event_type_elem is None:
                duration = alert.find(".//DurationList/Duration")
                if duration is not None:
                    event_type_elem = duration.find(".//relationEvent")
            # Method 5: Search by local name (strip namespace)
            if event_type_elem is None:
                for elem in alert.iter():
                    local_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if local_name == "eventType":
                        event_type_elem = elem
                        break
            # Method 6: Check if it's a direct child of alert
            if event_type_elem is None:
                for child in alert:
                    local_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if local_name == "eventType":
                        event_type_elem = child
                        break
            
            if event_type_elem is None:
                # Log the XML structure for debugging
                _LOGGER.error("No eventType found. Alert XML structure: %s", ET.tostring(alert, encoding='unicode')[:1000])
                all_tags = [elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag for elem in alert.iter()]
                _LOGGER.error("All tags in alert: %s", all_tags[:30])
                raise ValueError("No eventType found")
            
            event_id = event_type_elem.text.strip().lower() if event_type_elem.text else ""
            _LOGGER.info("Received event type: %s (raw)", event_id)
            
            # Handle duration events (version 2.0 notifications)
            # When eventType is "duration" or empty, the actual event type is in DurationList
            if not event_id or event_id == "duration":
                # Try with namespace first
                duration = alert.find(f".//{XML_NS}DurationList/{XML_NS}Duration")
                if duration is not None:
                    relation_event = duration.find(f"{XML_NS}relationEvent")
                    if relation_event is None:
                        relation_event = duration.find(".//relationEvent")
                    if relation_event is not None and relation_event.text:
                        event_id = relation_event.text.strip().lower()
                        _LOGGER.info("Extracted event type from DurationList: %s", event_id)
                
                # Try without namespace if still not found
                if not event_id or event_id == "duration":
                    duration = alert.find(".//DurationList/Duration")
                    if duration is not None:
                        relation_event = duration.find("relationEvent")
                        if relation_event is None:
                            relation_event = duration.find(".//relationEvent")
                        if relation_event is not None and relation_event.text:
                            event_id = relation_event.text.strip().lower()
                            _LOGGER.info("Extracted event type from DurationList (no namespace): %s", event_id)
                
                # If we still can't extract the event type, skip this notification
                # This happens when DurationList exists but relationEvent is missing/invalid
                if not event_id or event_id == "duration":
                    _LOGGER.debug("Cannot extract event type from DurationList, skipping notification")
                    raise ValueError("Cannot extract event type from DurationList")
            
            # Handle alternate event type mapping
            if EVENTS_ALTERNATE_ID.get(event_id):
                original_id = event_id
                event_id = EVENTS_ALTERNATE_ID[event_id]
                _LOGGER.info("Mapped event type %s -> %s", original_id, event_id)
            
            channel_id_elem = alert.find(f".//{XML_NS}channelID")
            if channel_id_elem is None:
                channel_id_elem = alert.find(f".//{XML_NS}dynChannelID")
            channel_id = int(channel_id_elem.text.strip()) if channel_id_elem is not None else 0
            
            # Get IO port ID (check both inputIOPortID and dynInputIOPortID)
            io_port_id_elem = alert.find(f".//{XML_NS}inputIOPortID")
            if io_port_id_elem is None or not io_port_id_elem.text:
                io_port_id_elem = alert.find(f".//{XML_NS}dynInputIOPortID")
            io_port_id = int(io_port_id_elem.text.strip()) if io_port_id_elem is not None and io_port_id_elem.text else 0
            
            # Get serial number or MAC address
            device_serial = None
            mac = ""
            
            serial_elem = alert.find(f".//{XML_NS}Extensions/{XML_NS}serialNumber")
            if serial_elem is not None:
                device_serial = serial_elem.text.strip() if serial_elem.text else None
            
            mac_elem = alert.find(f".//{XML_NS}macAddress")
            if mac_elem is not None:
                mac = mac_elem.text.strip() if mac_elem.text else ""
            
            # Get detection target and region ID (for smart events)
            detection_target = None
            region_id = 0
            
            region_elem = alert.find(f".//{XML_NS}DetectionRegionList/{XML_NS}DetectionRegionEntry")
            if region_elem is not None:
                target_elem = region_elem.find(f".//{XML_NS}detectionTarget")
                if target_elem is not None:
                    detection_target = target_elem.text.strip() if target_elem.text else None
                
                region_id_elem = region_elem.find(f".//{XML_NS}regionID")
                if region_id_elem is not None:
                    region_id = int(region_id_elem.text.strip()) if region_id_elem.text else 0
            
            # Check for activeState to determine if event is starting or ending
            # Some cameras send activeState="inactive" when event ends
            active_state = None
            active_state_elem = alert.find(f".//{XML_NS}activeState")
            if active_state_elem is None:
                active_state_elem = alert.find(".//activeState")
            if active_state_elem is not None and active_state_elem.text:
                active_state = active_state_elem.text.strip().lower()
            
            # Check if event is supported
            from .const import EVENTS
            if not EVENTS.get(event_id):
                _LOGGER.warning("Unsupported event type: %s (channel: %s, io_port: %s)", 
                             event_id, channel_id, io_port_id)
                raise ValueError(f"Unsupported event {event_id}")
            
            _LOGGER.info("Parsed event: type=%s, channel=%s, io_port=%s, activeState=%s", 
                        event_id, channel_id, io_port_id, active_state)
            
            return AlertInfo(
                channel_id=channel_id,
                io_port_id=io_port_id,
                event_id=event_id,
                device_serial_no=device_serial,
                mac=mac,
                region_id=region_id,
                detection_target=detection_target,
                active_state=active_state,
            )
        except Exception as e:
            # DurationList errors are expected - log as warning with XML detail
            if "Cannot extract event type from DurationList" in str(e):
                # Try to extract and show DurationList section specifically
                try:
                    root = ET.fromstring(xml)
                    alert = root.find(".//EventNotificationAlert")
                    if alert is None:
                        alert = root
                    
                    # Try to find DurationList with namespace
                    XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
                    duration_list = alert.find(f".//{XML_NS}DurationList")
                    if duration_list is None:
                        # Try without namespace
                        duration_list = alert.find(".//DurationList")
                    if duration_list is None:
                        # Try with ISAPI namespace (some cameras use this)
                        isapi_ns = "{http://www.isapi.org/ver20/XMLSchema}"
                        duration_list = alert.find(f".//{isapi_ns}DurationList")
                    
                    if duration_list is not None:
                        duration_xml = ET.tostring(duration_list, encoding='unicode')
                        event_type_elem = alert.find(f".//{XML_NS}eventType")
                        if event_type_elem is None:
                            event_type_elem = alert.find(".//eventType")
                        event_type = event_type_elem.text if event_type_elem is not None and event_type_elem.text else "missing"
                        _LOGGER.warning(
                            "Cannot extract event type from DurationList (expected for some camera notifications). "
                            "eventType=%s, DurationList XML: %s",
                            event_type, duration_xml
                        )
                    else:
                        # DurationList not found at all
                        alert_xml = ET.tostring(alert, encoding='unicode')[:800]
                        _LOGGER.warning(
                            "Cannot extract event type from DurationList - DurationList element not found. "
                            "Alert XML (first 800 chars): %s",
                            alert_xml
                        )
                except Exception as parse_err:
                    xml_snippet = xml[:800] if len(xml) > 800 else xml
                    _LOGGER.warning(
                        "Cannot extract event type from DurationList (expected for some camera notifications). "
                        "Failed to parse XML for detail. Raw XML (first 800 chars): %s, Parse error: %s",
                        xml_snippet, parse_err
                    )
            else:
                _LOGGER.error("Failed to parse event notification: %s", e)
            raise

    def trigger_sensor(self, entry, alert: AlertInfo) -> None:
        """Determine entity and set binary sensor state."""
        _LOGGER.debug("Alert: %s", alert)

        device_data = self.hass.data[DOMAIN][entry.entry_id]
        device_info = device_data.get("device_info", {})
        host = device_data.get("host", entry.data.get("host", ""))
        device_name = device_info.get("deviceName", host)
        from homeassistant.util import slugify
        
        # Build unique_id matching binary sensor format (using device name, NO prefix - ENTITY_ID_FORMAT adds it)
        # Format must match exactly what binary_sensor.py creates
        device_id_param = f"_{alert.channel_id}" if alert.channel_id != 0 and alert.event_id != EVENT_IO else ""
        # For I/O events: always include io_port_id (even if 0) to match binary_sensor format
        # For other events: don't include io_port_id (should be 0 anyway)
        if alert.event_id == EVENT_IO:
            io_port_id_param = f"_{alert.io_port_id}"  # I/O events always include io_port_id
        else:
            io_port_id_param = ""  # Non-I/O events don't include io_port_id
        unique_id = f"{slugify(device_name.lower())}{device_id_param}{io_port_id_param}_{alert.event_id}"

        _LOGGER.info("Looking for entity with unique_id: %s (event: %s, channel: %s, io_port: %s)", 
                     unique_id, alert.event_id, alert.channel_id, alert.io_port_id)

        entity_registry = async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, unique_id)
        if entity_id:
            entity = self.hass.states.get(entity_id)
            if entity:
                current_state = entity.state
                
                # Check activeState: "inactive" means event ended, otherwise it's starting/active
                if alert.active_state and alert.active_state.lower() == "inactive":
                    # Only clear if currently ON (state change)
                    if current_state == STATE_ON:
                        _LOGGER.info("Clearing entity: %s (event: %s, activeState: inactive)", entity_id, alert.event_id)
                        self.hass.states.async_set(entity_id, STATE_OFF, entity.attributes)
                    else:
                        _LOGGER.debug("Entity %s already OFF, ignoring inactive notification", entity_id)
                else:
                    # Only trigger if currently OFF (state change) - prevents duplicate notifications during continuous detection
                    if current_state == STATE_OFF:
                        _LOGGER.info("Triggering entity: %s (event: %s, activeState: %s)", 
                                   entity_id, alert.event_id, alert.active_state or "active")
                        self.hass.states.async_set(entity_id, STATE_ON, entity.attributes)
                        self.fire_hass_event(entry, alert)
                    else:
                        _LOGGER.debug("Entity %s already ON, ignoring duplicate active notification", entity_id)
                return
        
        # Fallback: If lookup failed with channel_id=0, try with channel_id=1 (for single cameras)
        # Some cameras send notifications with channel_id=0 but entities are created with channel_id=1
        if not entity_id and alert.channel_id == 0 and alert.event_id != EVENT_IO:
            device_data = self.hass.data[DOMAIN][entry.entry_id]
            cameras = device_data.get("cameras", [])
            # Try with channel_id=1 (first camera)
            if cameras:
                camera_id = cameras[0].get("id", 1)
                if camera_id != 0:
                    fallback_device_id_param = f"_{camera_id}"
                    fallback_unique_id = f"{slugify(device_name.lower())}{fallback_device_id_param}_{alert.event_id}"
                    entity_id = entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, fallback_unique_id)
                    if entity_id:
                        entity = self.hass.states.get(entity_id)
                        if entity:
                            current_state = entity.state
                            
                            # Check activeState: "inactive" means event ended, otherwise it's starting/active
                            if alert.active_state and alert.active_state.lower() == "inactive":
                                # Only clear if currently ON (state change)
                                if current_state == STATE_ON:
                                    _LOGGER.info("Clearing entity with fallback channel_id=%d: %s (event: %s, activeState: inactive)", 
                                               camera_id, entity_id, alert.event_id)
                                    self.hass.states.async_set(entity_id, STATE_OFF, entity.attributes)
                                else:
                                    _LOGGER.debug("Entity %s already OFF, ignoring inactive notification", entity_id)
                            else:
                                # Only trigger if currently OFF (state change) - prevents duplicate notifications during continuous detection
                                if current_state == STATE_OFF:
                                    _LOGGER.info("Triggering entity with fallback channel_id=%d: %s (event: %s, activeState: %s)", 
                                               camera_id, entity_id, alert.event_id, alert.active_state or "active")
                                    self.hass.states.async_set(entity_id, STATE_ON, entity.attributes)
                                    self.fire_hass_event(entry, alert)
                                else:
                                    _LOGGER.debug("Entity %s already ON, ignoring duplicate active notification", entity_id)
                            return
        
        raise ValueError(f"Entity not found {unique_id}")

    def fire_hass_event(self, entry, alert: AlertInfo):
        """Fire HASS event for Hikvision camera events."""
        device_info = self.hass.data[DOMAIN][entry.entry_id].get("device_info", {})
        camera_name = device_info.get("deviceName", "")

        message = {
            "channel_id": alert.channel_id,
            "io_port_id": alert.io_port_id,
            "camera_name": camera_name,
            "event_id": alert.event_id,
        }
        if alert.detection_target:
            message["detection_target"] = alert.detection_target
            message["region_id"] = alert.region_id

        self.hass.bus.fire(
            HIKVISION_EVENT,
            message,
        )

