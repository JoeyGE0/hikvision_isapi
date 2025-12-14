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
    """Return diagnostics for a config entry.
    
    This function must never raise exceptions - it should always return a dict,
    even if empty, to prevent breaking the integration.
    """
    try:
        if entry.entry_id not in hass.data.get(DOMAIN, {}):
            return {"error": "Entry not found in data"}
        
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
        
        # Get detailed capabilities XML info (fail gracefully - never break integration)
        capabilities_details = {}
        try:
            if api:
                # Get raw capabilities XML to extract more details
                import xml.etree.ElementTree as ET
                XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
                
                try:
                    xml = await hass.async_add_executor_job(api._get, "/ISAPI/System/capabilities")
                    
                    # Extract key capability flags
                    capabilities_details = {
                        "supplement_light": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportSupplementLight"),
                        "two_way_audio": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}AudioCap/{XML_NS}isSupportTwoWayAudio"),
                        "ir_cut_filter": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportIRCutFilter"),
                        "audio_alarm": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}EventCap/{XML_NS}isSupportAudioAlarm"),
                        "smart_detection": xml.find(f".//{XML_NS}SysCap/{XML_NS}SmartCap") is not None if xml is not None else None,
                        "image_adjustment": xml.find(f".//{XML_NS}SysCap/{XML_NS}ImageCap") is not None if xml is not None else None,
                        "io_inputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOInputPortNums"),
                        "io_outputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOOutputPortNums"),
                        "analog_inputs": _extract_capability_int(xml, f".//{XML_NS}SysCap/{XML_NS}VideoCap/{XML_NS}videoInputPortNums"),
                        "digital_inputs": _extract_capability_int(xml, f".//{XML_NS}RacmCap/{XML_NS}inputProxyNums"),
                        "holiday_mode": _extract_capability_bool(xml, f".//{XML_NS}SysCap/{XML_NS}isSupportHolidy"),
                    }
                except Exception as e:
                    capabilities_details["error"] = f"Failed to fetch capabilities XML: {str(e)}"
        except Exception as e:
            capabilities_details["error"] = f"Failed to get capabilities details: {str(e)}"
        
        # Get endpoint information (what endpoints are available) - fail gracefully
        endpoints_info = {}
        try:
            if api:
                endpoints_info = _get_endpoints_info(api, hass)
        except Exception as e:
            endpoints_info["error"] = str(e)
        
        # Get log server information - fail gracefully
        log_server_info = {}
        try:
            if api:
                log_server_info = await _get_log_server_info(api, hass)
        except Exception as e:
            log_server_info["error"] = str(e)
        
        # Camera/channel details - fail gracefully
        camera_details = []
        try:
            for cam in cameras:
                cam_info = {
                    "id": cam.get("id", "unknown") if isinstance(cam, dict) else "unknown",
                    "name": cam.get("name", "unknown") if isinstance(cam, dict) else "unknown",
                    "channel": cam.get("channel", "unknown") if isinstance(cam, dict) else "unknown",
                }
                # Add stream info if available
                if isinstance(cam, dict) and "streams" in cam:
                    try:
                        cam_info["streams"] = [
                            {"id": s.get("id"), "type": s.get("type"), "type_id": s.get("type_id")}
                            for s in cam.get("streams", []) if isinstance(s, dict)
                        ]
                    except Exception:
                        pass
                camera_details.append(cam_info)
        except Exception:
            camera_details = [{"error": "Failed to parse camera details"}]
        
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
            "log_server": log_server_info,
            "events": {
                "supported_events_count": len(supported_events),
                "supported_events": supported_events[:20] if len(supported_events) > 20 else supported_events,  # Limit to first 20
            },
        }
        
        return diagnostics
    except Exception as e:
        # Never let diagnostics break the integration - return error info instead
        return {
            "error": "Failed to generate diagnostics",
            "error_message": str(e),
            "error_type": type(e).__name__,
        }


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
    try:
        if not api or not hasattr(api, 'host') or not hasattr(api, 'channel'):
            return {"error": "API not available"}
        
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
                "ircut_filter": f"/ISAPI/Image/channels/{api.channel}/IrcutFilter",
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
    except Exception as e:
        return {"error": f"Failed to get endpoint info: {str(e)}"}


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


async def _get_log_server_info(api, hass) -> dict[str, Any]:
    """Get log server configuration and capabilities."""
    try:
        if not api or not hasattr(api, 'host'):
            return {"error": "API not available"}
        
        import xml.etree.ElementTree as ET
        XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
        
        # Get log server config
        log_server_config = {}
        try:
            xml = await hass.async_add_executor_job(api._get, "/ISAPI/System/logServer")
            if xml is not None:
                enabled = xml.find(f".//{XML_NS}enabled")
                addressing = xml.find(f".//{XML_NS}addressingFormatType")
                hostname = xml.find(f".//{XML_NS}hostName")
                ip_address = xml.find(f".//{XML_NS}ipAddress")
                port = xml.find(f".//{XML_NS}portNo")
                
                log_server_config = {
                    "enabled": enabled.text.strip().lower() == "true" if enabled is not None and enabled.text else False,
                    "addressing_format": addressing.text.strip() if addressing is not None and addressing.text else None,
                    "hostname": hostname.text.strip() if hostname is not None and hostname.text else None,
                    "ip_address": anonymise_ip(ip_address.text.strip()) if ip_address is not None and ip_address.text else None,
                    "port": port.text.strip() if port is not None and port.text else None,
                }
        except Exception as e:
            log_server_config["error"] = f"Failed to get log server config: {str(e)}"
        
        # Get log server capabilities
        log_server_capabilities = {}
        try:
            xml = await hass.async_add_executor_job(api._get, "/ISAPI/System/logServer/capabilities")
            if xml is not None:
                enabled_cap = xml.find(f".//{XML_NS}enabled")
                addressing_cap = xml.find(f".//{XML_NS}addressingFormatType")
                port_cap = xml.find(f".//{XML_NS}portNo")
                
                log_server_capabilities = {
                    "enabled_supported": enabled_cap is not None,
                    "addressing_formats": addressing_cap.get("opt", "").split(",") if addressing_cap is not None and addressing_cap.get("opt") else [],
                    "port_range": {
                        "min": port_cap.get("@min") if port_cap is not None and port_cap.get("@min") else None,
                        "max": port_cap.get("@max") if port_cap is not None and port_cap.get("@max") else None,
                    } if port_cap is not None else None,
                }
        except Exception as e:
            log_server_capabilities["error"] = f"Failed to get log server capabilities: {str(e)}"
        
        return {
            "config": log_server_config,
            "capabilities": log_server_capabilities,
            "endpoints": {
                "config": "/ISAPI/System/logServer",
                "capabilities": "/ISAPI/System/logServer/capabilities",
                "test": "/ISAPI/System/logServer/test",
            },
        }
    except Exception as e:
        return {"error": f"Failed to get log server info: {str(e)}"}

