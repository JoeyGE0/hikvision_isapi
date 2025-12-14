"""Diagnostics support for Hikvision ISAPI integration."""

from __future__ import annotations

import random
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


def anonymise_ip(original: str) -> str:
    """Anonymise IP address."""
    parts = original.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.xxx.xxx"
    return "xxx.xxx.xxx.xxx"


def anonymise_mac(original: str) -> str:
    """Anonymise MAC address."""
    mac = [random.randint(0x00, 0xFF) for _ in range(6)]
    return ":".join("%02x" % x for x in mac)


def anonymise_serial(original: str) -> str:
    """Anonymise serial number."""
    return "".join("0" if c.isdigit() else c for c in original)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if entry.entry_id not in hass.data[DOMAIN]:
        return {}
    
    data = hass.data[DOMAIN][entry.entry_id]
    api = data.get("api")
    device_info = data.get("device_info", {})
    capabilities = data.get("capabilities", {})
    detected_features = data.get("detected_features", {})
    cameras = data.get("cameras", [])
    supported_events = data.get("supported_events", [])
    
    # Anonymize sensitive data
    host = data.get("host", "")
    anonymized_host = anonymise_ip(host) if host else ""
    
    # Get detailed capabilities XML info
    capabilities_details = {}
    try:
        if api:
            # Get raw capabilities XML to extract more details
            import xml.etree.ElementTree as ET
            XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
            
            xml = await hass.async_add_executor_job(api._get, "/ISAPI/System/capabilities")
            
            # Extract key capability flags
            capabilities_details = {
                "supplement_light": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportSupplementLight"),
                "two_way_audio": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}AudioCap/{XML_NS}isSupportTwoWayAudio"),
                "ir_cut_filter": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportIRCutFilter"),
                "audio_alarm": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}EventCap/{XML_NS}isSupportAudioAlarm"),
                "smart_detection": xml.find(f".//{XML_NS}SysCap/{XML_NS}SmartCap") is not None,
                "image_adjustment": xml.find(f".//{XML_NS}SysCap/{XML_NS}ImageCap") is not None,
                "io_inputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOInputPortNums"),
                "io_outputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOOutputPortNums"),
                "analog_inputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}VideoCap/{XML_NS}videoInputPortNums"),
                "digital_inputs": _extract_capability_int(xml, f".//{XML_NS}RacmCap/{XML_NS}inputProxyNums"),
                "holiday_mode": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}isSupportHolidy"),
            }
    except Exception as e:
        capabilities_details["error"] = str(e)
    
    # Get endpoint information (what endpoints are available)
    endpoints_info = _get_endpoints_info(api, hass) if api else {}
    
    # Camera/channel details
    camera_details = []
    for cam in cameras:
        cam_info = {
            "id": cam.get("id", "unknown"),
            "name": cam.get("name", "unknown"),
            "channel": cam.get("channel", "unknown"),
        }
        # Add stream info if available
        if "streams" in cam:
            cam_info["streams"] = [
                {"id": s.get("id"), "type": s.get("type"), "type_id": s.get("type_id")}
                for s in cam.get("streams", [])
            ]
        camera_details.append(cam_info)
    
    diagnostics = {
        "integration": {
            "version": "1.0.0",  # Update this if you track version
            "host": anonymized_host,
            "device_name": device_info.get("deviceName", "Unknown"),
        },
        "device_info": {
            "manufacturer": device_info.get("manufacturer", "Unknown"),
            "model": device_info.get("model", "Unknown"),
            "firmware_version": device_info.get("firmwareVersion", "Unknown"),
            "hardware_version": device_info.get("hardwareVersion", "Unknown"),
            "serial_number": anonymise_serial(device_info.get("serialNumber", "")) if device_info.get("serialNumber") else "Unknown",
            "mac_address": anonymise_mac(device_info.get("macAddress", "")) if device_info.get("macAddress") else "Unknown",
        },
        "capabilities": {
            "is_nvr": capabilities.get("is_nvr", False),
            "channel_count": len(cameras),
            "analog_cameras": capabilities.get("analog_cameras_inputs", 0),
            "digital_cameras": capabilities.get("digital_cameras_inputs", 0),
            "input_ports": capabilities.get("input_ports", 0),
            "output_ports": capabilities.get("output_ports", 0),
            "holiday_mode": capabilities.get("support_holiday_mode", False),
            "detailed_capabilities": capabilities_details,
        },
        "cameras": camera_details,
        "detected_features": {
            "total_features_tested": len(detected_features),
            "supported_features": sum(1 for v in detected_features.values() if v),
            "unsupported_features": sum(1 for v in detected_features.values() if not v),
            "feature_details": detected_features,
        },
        "supported_entities": {
            "number_entities": _count_supported_number_entities(detected_features),
            "switch_entities": _count_supported_switch_entities(detected_features),
            "select_entities": _count_supported_select_entities(detected_features),
            "media_player": detected_features.get("media_player", False),
            "button_entities": _count_supported_button_entities(detected_features),
        },
        "endpoints": endpoints_info,
        "events": {
            "supported_events_count": len(supported_events),
            "supported_events": supported_events[:20] if len(supported_events) > 20 else supported_events,  # Limit to first 20
        },
    }
    
    return diagnostics


def _extract_capability_bool(xml, xpath: str) -> bool | None:
    """Extract boolean capability from XML."""
    try:
        elem = xml.find(xpath)
        if elem is not None and elem.text:
            return elem.text.strip().lower() == "true"
        return None
    except Exception:
        return None


def _extract_capability_int(xml, xpath: str) -> int | None:
    """Extract integer capability from XML."""
    try:
        elem = xml.find(xpath)
        if elem is not None and elem.text:
            return int(elem.text.strip())
        return None
    except Exception:
        return None


def _get_endpoints_info(api, hass) -> dict[str, Any]:
    """Get information about available ISAPI endpoints."""
    endpoints = {
        "base_urls": {
            "image_channels": f"http://{api.host}/ISAPI/Image/channels/{api.channel}",
            "system": f"http://{api.host}/ISAPI/System",
            "smart": f"http://{api.host}/ISAPI/Smart",
            "event": f"http://{api.host}/ISAPI/Event",
            "streaming": f"http://{api.host}/ISAPI/Streaming",
        },
        "common_endpoints": {
            "device_info": "/ISAPI/System/deviceInfo",
            "capabilities": "/ISAPI/System/capabilities",
            "two_way_audio": f"/ISAPI/System/TwoWayAudio/channels/{api.channel}",
            "supplement_light": f"/ISAPI/Image/channels/{api.channel}/supplementLight",
            "ircut_filter": f"/ISAPI/Image/channels/{api.channel}/ircutFilter",
            "color_settings": f"/ISAPI/Image/channels/{api.channel}/color",
            "sharpness": f"/ISAPI/Image/channels/{api.channel}/sharpness",
            "motion_detection": f"/ISAPI/Smart/Image/{api.channel}/motionDetection",
            "tamper_detection": f"/ISAPI/Smart/Image/{api.channel}/tamperDetection",
            "field_detection": f"/ISAPI/Smart/Image/{api.channel}/fieldDetection",
            "line_detection": f"/ISAPI/Smart/Image/{api.channel}/lineDetection",
            "scene_change": f"/ISAPI/Smart/Image/{api.channel}/sceneChangeDetection",
            "region_entrance": f"/ISAPI/Smart/Image/{api.channel}/regionEntrance",
            "region_exiting": f"/ISAPI/Smart/Image/{api.channel}/regionExiting",
            "io_inputs": f"/ISAPI/System/IO/inputs/{api.channel}",
            "io_outputs": f"/ISAPI/System/IO/outputs/{api.channel}",
            "audio_alarm": "/ISAPI/Event/triggers/notifications/AudioAlarm?format=json",
            "streaming_channels": f"/ISAPI/Streaming/channels",
        },
        "note": "These are the endpoints used by the integration. Test endpoints by adding ?format=json for JSON or leaving as XML.",
    }
    return endpoints


def _count_supported_number_entities(features: dict) -> int:
    """Count supported number entities."""
    number_features = [
        "ir_sensitivity", "ir_filter_time", "speaker_volume", "microphone_volume",
        "white_light_time", "white_light_brightness", "ir_light_brightness",
        "white_light_brightness_limit", "ir_light_brightness_limit",
        "motion_sensitivity", "motion_start_trigger_time", "motion_end_trigger_time",
        "brightness", "contrast", "saturation", "sharpness",
        "alarm_times", "loudspeaker_volume"
    ]
    return sum(1 for f in number_features if features.get(f, False))


def _count_supported_switch_entities(features: dict) -> int:
    """Count supported switch entities."""
    switch_features = [
        "noise_reduce", "motion_detection", "tamper_detection", "intrusion_detection",
        "line_crossing_detection", "scene_change_detection", "region_entrance_detection",
        "region_exiting_detection", "alarm_input", "alarm_output"
    ]
    return sum(1 for f in switch_features if features.get(f, False))


def _count_supported_select_entities(features: dict) -> int:
    """Count supported select entities."""
    select_features = [
        "supplement_light_mode", "day_night_mode", "motion_detection",
        "audio_alarm_type", "audio_alarm_sound"
    ]
    # day_night_mode enables 2 entities (BrightnessControl and IRMode)
    count = sum(1 for f in select_features if features.get(f, False))
    if features.get("day_night_mode", False):
        count += 1  # day_night_mode enables 2 entities
    return count


def _count_supported_button_entities(features: dict) -> int:
    """Count supported button entities."""
    button_features = ["restart", "media_player", "test_audio_alarm"]
    return sum(1 for f in button_features if features.get(f, False))

