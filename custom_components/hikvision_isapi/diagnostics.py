"""Diagnostics support for Hikvision ISAPI integration."""

from __future__ import annotations

import random
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .diagnostics_snapshot import (
    async_refresh_diagnostics_snapshot,
    diagnostics_signature,
    integration_version,
)


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


def _count_supported_number_entities(features: dict) -> int:
    number_features = [
        "ir_sensitivity", "ir_filter_time", "speaker_volume", "microphone_volume",
        "white_light_time", "white_light_brightness", "ir_light_brightness",
        "white_light_brightness_limit", "ir_light_brightness_limit",
        "motion_sensitivity", "motion_start_trigger_time", "motion_end_trigger_time",
        "brightness", "contrast", "saturation", "sharpness",
        "alarm_times", "loudspeaker_volume",
    ]
    return sum(1 for f in number_features if features.get(f, False))


def _count_supported_switch_entities(features: dict) -> int:
    switch_features = [
        "noise_reduce", "motion_detection", "tamper_detection", "intrusion_detection",
        "line_crossing_detection", "scene_change_detection", "defocus_detection",
        "region_entrance_detection", "region_exiting_detection", "alarm_input", "alarm_output",
    ]
    return sum(1 for f in switch_features if features.get(f, False))


def _count_supported_select_entities(features: dict) -> int:
    select_features = [
        "supplement_light_mode", "day_night_mode", "motion_detection",
        "audio_alarm_type", "audio_alarm_sound",
    ]
    count = sum(1 for f in select_features if features.get(f, False))
    if features.get("day_night_mode", False):
        count += 1
    return count


def _count_supported_button_entities(features: dict) -> int:
    button_features = ["restart", "media_player", "test_audio_alarm"]
    return sum(1 for f in button_features if features.get(f, False))


def _entity_registry_summary(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Local HA registry only — no camera HTTP."""
    registry = er.async_get(hass)
    binary_sensors = []
    for entity in registry.entities.values():
        if entity.config_entry_id != entry.entry_id:
            continue
        if not entity.entity_id.startswith("binary_sensor."):
            continue
        binary_sensors.append(
            {
                "entity_id": entity.entity_id,
                "unique_id": entity.unique_id,
                "disabled": entity.disabled_by is not None,
            }
        )
    return {
        "binary_sensor_count": len(binary_sensors),
        "binary_sensors": binary_sensors[:40],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Camera endpoint probes live in a cached snapshot built at setup / capability reload.
    Downloading this file does not ping the camera unless the cache is missing or stale
    (features/events changed without a reload).
    """
    try:
        if entry.entry_id not in hass.data.get(DOMAIN, {}):
            return {"error": "Entry not found in data"}

        data = hass.data[DOMAIN][entry.entry_id]
        device_info = data.get("device_info", {})
        capabilities = data.get("capabilities", {})
        detected_features = data.get("detected_features", {})
        cameras = data.get("cameras", [])
        supported_events = data.get("supported_events", [])

        host = data.get("host", "")
        anonymized_host = anonymise_ip(host) if host else ""

        current_sig = diagnostics_signature(detected_features, supported_events)
        snapshot = data.get("diagnostics_snapshot") or {}

        if not snapshot or snapshot.get("signature") != current_sig:
            refreshed = await async_refresh_diagnostics_snapshot(
                hass, entry, trigger="diagnostics_stale"
            )
            if refreshed:
                snapshot = refreshed

        camera_details = []
        for cam in cameras:
            if not isinstance(cam, dict):
                continue
            camera_details.append(
                {
                    "id": cam.get("id", "unknown"),
                    "name": cam.get("name", "unknown"),
                    "channel": cam.get("channel", "unknown"),
                }
            )

        events_block = dict(snapshot.get("events") or {})
        events_block["live_supported_events_count"] = len(supported_events)

        return {
            "integration": {
                "version": integration_version(),
                "host": anonymized_host,
                "device_name": device_info.get("deviceName", "Unknown"),
            },
            "diagnostics_cache": {
                "built_at": snapshot.get("built_at"),
                "trigger": snapshot.get("trigger"),
                "signature": snapshot.get("signature"),
                "note": (
                    "Endpoint probes run at setup and when capabilities change (entity add/remove). "
                    "Not on coordinator ticks. Download uses this cache unless stale."
                ),
            },
            "device_info": {
                "manufacturer": device_info.get("manufacturer", "Unknown"),
                "model": device_info.get("model", "Unknown"),
                "firmware_version": device_info.get("firmwareVersion", "Unknown"),
                "hardware_version": device_info.get("hardwareVersion", "Unknown"),
                "serial_number": anonymise_serial(device_info.get("serialNumber", ""))
                if device_info.get("serialNumber")
                else "Unknown",
                "mac_address": anonymise_mac(device_info.get("macAddress", ""))
                if device_info.get("macAddress")
                else "Unknown",
            },
            "capabilities": {
                "is_nvr": capabilities.get("is_nvr", False),
                "channel_count": len(cameras),
                "input_ports": capabilities.get("input_ports", 0),
                "output_ports": capabilities.get("output_ports", 0),
                "xml_flags_at_snapshot": snapshot.get("capabilities_xml_flags", {}),
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
            "endpoint_probes": snapshot.get("endpoint_probes", {}),
            "events": events_block,
            "alarm_server": snapshot.get("alarm_server", {}),
            "entities": _entity_registry_summary(hass, entry),
        }
    except Exception as e:
        return {
            "error": "Failed to generate diagnostics",
            "error_message": str(e),
            "error_type": type(e).__name__,
        }
