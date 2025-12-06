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
from homeassistant.const import CONTENT_TYPE_TEXT_PLAIN, STATE_ON, Platform
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

        try:
            _LOGGER.debug("--- Incoming event notification ---")
            _LOGGER.debug("Source: %s", request.remote)
            xml = await self.parse_event_request(request)
            _LOGGER.debug("alert info: %s", xml[:500])
            alert = self.parse_event_notification(xml)
            device_entry = self.get_isapi_device(request.remote, alert)
            self.trigger_sensor(device_entry, alert)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Cannot process incoming event %s", ex)

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
            
            alert = root.find(f".//{XML_NS}EventNotificationAlert")
            if alert is None:
                raise ValueError("No EventNotificationAlert found")
            
            event_type_elem = alert.find(f".//{XML_NS}eventType")
            if event_type_elem is None:
                # Check for DurationList (version 2.0)
                duration = alert.find(f".//{XML_NS}DurationList/{XML_NS}Duration")
                if duration is not None:
                    event_type_elem = duration.find(f".//{XML_NS}relationEvent")
            
            if event_type_elem is None:
                raise ValueError("No eventType found")
            
            event_id = event_type_elem.text.strip().lower()
            
            # Handle alternate event type
            if EVENTS_ALTERNATE_ID.get(event_id):
                event_id = EVENTS_ALTERNATE_ID[event_id]
            
            channel_id_elem = alert.find(f".//{XML_NS}channelID")
            if channel_id_elem is None:
                channel_id_elem = alert.find(f".//{XML_NS}dynChannelID")
            channel_id = int(channel_id_elem.text.strip()) if channel_id_elem is not None else 0
            
            # Get IO port ID
            io_port_id_elem = alert.find(f".//{XML_NS}inputIOPortID")
            if io_port_id_elem is None:
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
            
            return AlertInfo(
                channel_id=channel_id,
                io_port_id=io_port_id,
                event_id=event_id,
                device_serial_no=device_serial,
                mac=mac,
                region_id=region_id,
                detection_target=detection_target,
            )
        except Exception as e:
            _LOGGER.error("Failed to parse event notification: %s", e)
            raise

    def trigger_sensor(self, entry, alert: AlertInfo) -> None:
        """Determine entity and set binary sensor state."""
        _LOGGER.debug("Alert: %s", alert)

        host = self.hass.data[DOMAIN][entry.entry_id].get("host", "")
        
        # Map event_id to unique_id suffix (matching your original naming convention)
        event_unique_id_map = {
            "motiondetection": "motion",
            "tamperdetection": "video_tampering",
            "videoloss": "video_loss",
            "scenechangedetection": "scene_change",
            "fielddetection": "intrusion",
            "linedetection": "line_crossing",
            "regionentrance": "region_entrance",
            "regionexiting": "region_exiting",
        }
        
        unique_id_suffix = event_unique_id_map.get(alert.event_id, alert.event_id)
        unique_id = f"{host}_{unique_id_suffix}"

        _LOGGER.debug("UNIQUE_ID: %s", unique_id)

        entity_registry = async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, unique_id)
        if entity_id:
            entity = self.hass.states.get(entity_id)
            if entity:
                self.hass.states.async_set(entity_id, STATE_ON, entity.attributes)
                self.fire_hass_event(entry, alert)
            else:
                _LOGGER.warning("Entity state not found for %s", entity_id)
        else:
            _LOGGER.warning("Entity not found in registry: %s", unique_id)

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

