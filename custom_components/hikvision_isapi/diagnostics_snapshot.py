"""Build and cache diagnostics snapshots (camera probes run only on setup / capability change)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .api import HikvisionISAPI
from .const import ALARM_SERVER_PATH
from .models import EventInfo

_LOGGER = logging.getLogger(__name__)

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"

# Probed once when the snapshot is built — not on a timer or diagnostics download.
_DIAGNOSTIC_PROBE_KEYS: tuple[tuple[str, str], ...] = (
    ("system_device_info", "/ISAPI/System/deviceInfo"),
    ("system_capabilities", "/ISAPI/System/capabilities"),
    ("event_triggers_bulk", "/ISAPI/Event/triggers"),
    ("event_channels_capabilities", "/ISAPI/Event/channels/capabilities"),
    ("event_http_hosts", "/ISAPI/Event/notification/httpHosts"),
    ("streaming_channels", "/ISAPI/Streaming/channels"),
)


def integration_version() -> str:
    """Read integration version from manifest.json."""
    try:
        manifest = Path(__file__).parent / "manifest.json"
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        return "unknown"


def _event_signature_key(event: EventInfo | dict) -> str:
    """Stable event id for diagnostics cache signatures."""
    serialized = _serialize_event(event)
    return f"{serialized['id']}:{serialized['channel_id']}"


def diagnostics_signature(detected_features: dict, supported_events: list) -> str:
    """Stable id for whether the cached snapshot still matches HA state."""
    event_part = sorted(
        _event_signature_key(e)
        for e in supported_events
        if isinstance(e, (EventInfo, dict))
    )
    payload = {
        "features": sorted((k, v) for k, v in (detected_features or {}).items()),
        "events": event_part,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _serialize_event(event: EventInfo | dict) -> dict[str, Any]:
    if isinstance(event, EventInfo):
        return {
            "id": event.id,
            "channel_id": event.channel_id,
            "io_port_id": event.io_port_id,
            "disabled": event.disabled,
            "is_proxy": event.is_proxy,
        }
    return {
        "id": event.get("id"),
        "channel_id": event.get("channel_id"),
        "io_port_id": event.get("io_port_id", 0),
        "disabled": event.get("disabled", False),
        "is_proxy": event.get("is_proxy", False),
    }


def _probe_list_for_channel(channel: int) -> tuple[tuple[str, str], ...]:
    return _DIAGNOSTIC_PROBE_KEYS + (
        ("motion_video_input", f"/ISAPI/System/Video/inputs/channels/{channel}/motionDetection"),
        (f"event_motion_trigger_{channel}", f"/ISAPI/Event/triggers/motiondetection-{channel}"),
        (f"event_tamper_trigger_{channel}", f"/ISAPI/Event/triggers/tamperdetection-{channel}"),
        (f"event_field_trigger_{channel}", f"/ISAPI/Event/triggers/fielddetection-{channel}"),
        (f"event_line_trigger_{channel}", f"/ISAPI/Event/triggers/linedetection-{channel}"),
        ("image_supplement_light", f"/ISAPI/Image/channels/{channel}/supplementLight"),
        ("image_ircut", f"/ISAPI/Image/channels/{channel}/IrcutFilter"),
        ("image_color", f"/ISAPI/Image/channels/{channel}/color"),
        ("smart_motion", f"/ISAPI/Smart/Image/{channel}/motionDetection"),
        ("smart_tamper", f"/ISAPI/Smart/Image/{channel}/tamperDetection"),
        ("smart_field", f"/ISAPI/Smart/Image/{channel}/fieldDetection"),
        ("smart_line", f"/ISAPI/Smart/Image/{channel}/lineDetection"),
        ("smart_field_detection_alt", f"/ISAPI/Smart/FieldDetection/{channel}"),
        ("two_way_audio", f"/ISAPI/System/TwoWayAudio/channels/{channel}"),
    )


def _center_linked_on_trigger(api: HikvisionISAPI, event_id: str, channel: int) -> dict[str, Any]:
    """Check Surveillance Center linkage on a readable event trigger (snapshot build only)."""
    for path in api._event_trigger_probe_paths(event_id, channel):
        status = api.probe_endpoint_status(path)
        if status != 200:
            continue
        try:
            xml = api._get(path)
        except Exception as err:
            return {"readable": False, "path": path, "status": status, "error": str(err)}

        event_trigger = xml.find(f".//{XML_NS}EventTrigger")
        if event_trigger is None and xml.tag.endswith("EventTrigger"):
            event_trigger = xml
        if event_trigger is None:
            return {"readable": True, "path": path, "center_linked": None}

        methods: list[str] = []
        for notif in event_trigger.findall(f".//{XML_NS}EventTriggerNotification"):
            method_elem = notif.find(f".//{XML_NS}notificationMethod")
            if method_elem is not None and method_elem.text:
                methods.append(method_elem.text.strip().lower())
        return {
            "readable": True,
            "path": path,
            "center_linked": "center" in methods,
            "notification_methods": methods,
        }
    return {"readable": False, "center_linked": None}


def _capabilities_xml_flags(api: HikvisionISAPI) -> dict[str, Any]:
    try:
        xml = api._get("/ISAPI/System/capabilities")
    except Exception as err:
        return {"error": str(err)}

    def _bool(xpath: str) -> bool | None:
        elem = xml.find(xpath)
        if elem is not None and elem.text:
            return elem.text.strip().lower() == "true"
        return None

    def _int(xpath: str) -> int | None:
        elem = xml.find(xpath)
        if elem is not None and elem.text:
            try:
                return int(elem.text.strip())
            except ValueError:
                return None
        return None

    return {
        "supplement_light": _bool(f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportSupplementLight"),
        "two_way_audio": _bool(f".//{XML_NS}SysCap/{XML_NS}AudioCap/{XML_NS}isSupportTwoWayAudio"),
        "ir_cut_filter": _bool(f".//{XML_NS}SysCap/{XML_NS}ImageCap/{XML_NS}isSupportIRCutFilter"),
        "audio_alarm": _bool(f".//{XML_NS}SysCap/{XML_NS}EventCap/{XML_NS}isSupportAudioAlarm"),
        "motion_event_cap": _bool(f".//{XML_NS}EventCap/{XML_NS}isSupportMotionDetection"),
        "tamper_event_cap": _bool(f".//{XML_NS}EventCap/{XML_NS}isSupportTamperDetection"),
        "smart_detection": xml.find(f".//{XML_NS}SysCap/{XML_NS}SmartCap") is not None,
        "io_inputs": _int(f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOInputPortNums"),
        "io_outputs": _int(f".//{XML_NS}SysCap/{XML_NS}IOCap/{XML_NS}IOOutputPortNums"),
    }


def _event_discovery_method(bulk_status: int | str, supported_events: list) -> str:
    if bulk_status == 200 and supported_events:
        return "bulk_triggers"
    if bulk_status == 200 and not supported_events:
        return "bulk_triggers_empty"
    if supported_events:
        return "fallback"
    return "none"


def build_diagnostics_snapshot(
    api: HikvisionISAPI,
    *,
    detected_features: dict,
    supported_events: list,
    trigger: str = "setup",
    alarm_server_configured: bool | None = None,
) -> dict[str, Any]:
    """Probe the camera once and cache results for diagnostics export.

    Called on integration setup and when capability reload runs (entities add/remove).
    Not called on coordinator ticks or diagnostics download.
    """
    channel = api.channel
    probes: dict[str, dict[str, Any]] = {}
    for key, path in _probe_list_for_channel(channel):
        status = api.probe_endpoint_status(path)
        probes[key] = {"path": path, "status": status}

    bulk_status = probes.get("event_triggers_bulk", {}).get("status")
    discovery_method = _event_discovery_method(bulk_status, supported_events)

    center_linkage = {}
    _event_feature_keys = {
        "motiondetection": "motion_detection",
        "tamperdetection": "tamper_detection",
        "fielddetection": "intrusion_detection",
        "linedetection": "line_crossing_detection",
    }
    for event_id, feat_key in _event_feature_keys.items():
        if detected_features.get(feat_key, False) or any(
            getattr(e, "id", None) == event_id for e in supported_events
        ):
            center_linkage[event_id] = _center_linked_on_trigger(api, event_id, channel)

    alarm_server: dict[str, Any] = {}
    try:
        raw = api.get_alarm_server()
        alarm_server = {
            "configured": bool(raw.get("host") or raw.get("path")),
            "path": raw.get("path"),
            "port": raw.get("port"),
            "protocol": raw.get("protocol"),
            "expected_ha_path": ALARM_SERVER_PATH,
            "integration_set_alarm_server": alarm_server_configured,
        }
    except Exception as err:
        alarm_server = {"error": str(err)}

    signature = diagnostics_signature(detected_features, supported_events)
    built_at = datetime.now(UTC).isoformat()

    snapshot = {
        "signature": signature,
        "built_at": built_at,
        "trigger": trigger,
        "integration_version": integration_version(),
        "endpoint_probes": probes,
        "capabilities_xml_flags": _capabilities_xml_flags(api),
        "events": {
            "bulk_triggers_status": bulk_status,
            "discovery_method": discovery_method,
            "supported_events_count": len(supported_events),
            "supported_events": [_serialize_event(e) for e in supported_events[:30]],
            "center_linkage": center_linkage,
        },
        "alarm_server": alarm_server,
    }
    _LOGGER.debug(
        "Diagnostics snapshot built for %s (trigger=%s, events=%d, bulk=%s)",
        api.host,
        trigger,
        len(supported_events),
        bulk_status,
    )
    return snapshot


async def async_refresh_diagnostics_snapshot(
    hass,
    entry,
    *,
    trigger: str = "setup",
) -> dict[str, Any] | None:
    """Build and store diagnostics snapshot (executor — camera HTTP only here)."""
    from homeassistant.config_entries import ConfigEntry

    from .const import CONF_SET_ALARM_SERVER, DOMAIN

    if not isinstance(entry, ConfigEntry):
        return None
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not domain_data:
        return None
    api = domain_data.get("api")
    if not api:
        return None

    snapshot = await hass.async_add_executor_job(
        build_diagnostics_snapshot,
        api,
        detected_features=domain_data.get("detected_features") or {},
        supported_events=domain_data.get("supported_events") or [],
        trigger=trigger,
        alarm_server_configured=entry.data.get(CONF_SET_ALARM_SERVER, True),
    )
    domain_data["diagnostics_snapshot"] = snapshot
    return snapshot
