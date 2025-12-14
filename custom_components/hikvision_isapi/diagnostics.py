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
    
    # Anonymize sensitive data
    host = data.get("host", "")
    anonymized_host = anonymise_ip(host) if host else ""
    
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
        },
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
    }
    
    return diagnostics


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

