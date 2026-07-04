"""Basic vs Advanced entity profiles for config flow and platform setup."""

from __future__ import annotations

from typing import Any, NamedTuple

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENTITY_GROUPS,
    CONF_ENTITY_ITEMS,
    CONF_ENTITY_KNOWN_SUPPORTED,
    CONF_INTEGRATION_PROFILE,
    CUSTOMIZE_SECTION_ITEMS_KEY,
    ENTITY_GROUP_AUDIO_ALARM,
    ENTITY_GROUP_ALARM_IO,
    ENTITY_GROUP_CAMERA,
    ENTITY_GROUP_DAY_NIGHT,
    ENTITY_GROUP_DETECTIONS,
    ENTITY_GROUP_DETECTION_SWITCHES,
    ENTITY_GROUP_ESSENTIAL_SYSTEM,
    ENTITY_GROUP_IMAGE_ADJUSTMENT,
    ENTITY_GROUP_MOTION_TUNING,
    ENTITY_GROUP_SIREN,
    ENTITY_GROUP_SUPPLEMENT_LIGHT,
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS,
    ENTITY_GROUP_TWO_WAY_AUDIO,
    EVENTS,
    EVENT_IO,
    PROFILE_ADVANCED,
    PROFILE_BASIC,
)

# Human-readable labels for the config-flow multi-select (translation keys in en.json).
ENTITY_GROUP_LABELS: dict[str, str] = {
    ENTITY_GROUP_DETECTIONS: "Event detections (binary sensors)",
    ENTITY_GROUP_CAMERA: "Camera streams",
    ENTITY_GROUP_ESSENTIAL_SYSTEM: "Uptime & maintenance",
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS: "System diagnostics (CPU, memory, streaming)",
    ENTITY_GROUP_DAY_NIGHT: "Day / night (IR cut)",
    ENTITY_GROUP_SUPPLEMENT_LIGHT: "Supplement light",
    ENTITY_GROUP_SIREN: "Siren (play alarm from HA)",
    ENTITY_GROUP_DETECTION_SWITCHES: "Detection enable switches",
    ENTITY_GROUP_MOTION_TUNING: "Motion tuning (sensitivity, target type)",
    ENTITY_GROUP_IMAGE_ADJUSTMENT: "Image adjustment (brightness, contrast, …)",
    ENTITY_GROUP_AUDIO_ALARM: "Audio alarm settings (tone, volume)",
    ENTITY_GROUP_TWO_WAY_AUDIO: "Two-way audio / speaker",
    ENTITY_GROUP_ALARM_IO: "Alarm input / output",
}

# Ordered list for stable UI.
ALL_ENTITY_GROUPS: tuple[str, ...] = tuple(ENTITY_GROUP_LABELS.keys())

# Core preset: what most people use (always included in Basic; also always on in Advanced).
BASIC_ENTITY_GROUPS: frozenset[str] = frozenset({
    ENTITY_GROUP_DETECTIONS,
    ENTITY_GROUP_CAMERA,
    ENTITY_GROUP_ESSENTIAL_SYSTEM,
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS,
})

# Within basic groups, only expose these items (None = all supported items in that group).
BASIC_ENTITY_ITEMS: dict[str, frozenset[str]] = {
    ENTITY_GROUP_ESSENTIAL_SYSTEM: frozenset({
        "device_uptime",
        "reboot_count",
        "firmware_update",
    }),
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS: frozenset({
        "cpu_utilization",
        "memory_usage",
    }),
}

# Auto-enable when newly supported; user can still turn off in customize.
DEFAULT_ON_ENTITY_ITEMS: dict[str, frozenset[str]] = {
    ENTITY_GROUP_DETECTIONS: frozenset({
        "motiondetection",
        "tamperdetection",
        "videoloss",
    }),
}

# Advanced adds optional groups on top of BASIC (day/night, volumes, IR tuning, siren, etc.).
ADVANCED_EXTRA_ENTITY_GROUPS: frozenset[str] = frozenset(
    g for g in ALL_ENTITY_GROUPS if g not in BASIC_ENTITY_GROUPS
)

# Basic groups with per-item picks on the Advanced customize screen (beyond the core preset).
ADVANCED_CUSTOMIZE_BASIC_GROUPS: tuple[str, ...] = (
    ENTITY_GROUP_DETECTIONS,
    ENTITY_GROUP_ESSENTIAL_SYSTEM,
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS,
)

# Every category shown on the Advanced entity_customize step (stable order).
CUSTOMIZE_FLOW_GROUPS: tuple[str, ...] = ADVANCED_CUSTOMIZE_BASIC_GROUPS + tuple(
    g for g in ALL_ENTITY_GROUPS if g in ADVANCED_EXTRA_ENTITY_GROUPS
)

EXTRA_ENTITY_GROUP_LABELS: dict[str, str] = {
    ENTITY_GROUP_DAY_NIGHT: "Day / night & IR cut controls",
    ENTITY_GROUP_SUPPLEMENT_LIGHT: "Supplement light (brightness, timers, limits)",
    ENTITY_GROUP_SIREN: "Siren (play alarm from HA)",
    ENTITY_GROUP_DETECTION_SWITCHES: "Detection on/off switches",
    ENTITY_GROUP_MOTION_TUNING: "Motion tuning (sensitivity, target type)",
    ENTITY_GROUP_IMAGE_ADJUSTMENT: "Image adjustment (brightness, contrast, …)",
    ENTITY_GROUP_AUDIO_ALARM: "Audio alarm (tone, volume, test button)",
    ENTITY_GROUP_TWO_WAY_AUDIO: "Two-way audio & speaker controls",
    ENTITY_GROUP_ALARM_IO: "Alarm input / output",
}

_DETECTION_EVENT_FEATURES: dict[str, tuple[str, str | None]] = {
    "motiondetection": ("Motion", "motion_detection"),
    "tamperdetection": ("Video tampering", "tamper_detection"),
    "fielddetection": ("Intrusion", "intrusion_detection"),
    "linedetection": ("Line crossing", "line_crossing_detection"),
    "scenechangedetection": ("Scene change", "scene_change_detection"),
    "regionentrance": ("Region entrance", "region_entrance_detection"),
    "regionexiting": ("Region exiting", "region_exiting_detection"),
    "defocus": ("Defocus", "defocus_detection"),
}

# detect_features keys ↔ event ids (same map as api._collect_events_from_detected_features).
FEATURE_KEY_TO_EVENT_ID: dict[str, str] = {
    feature_key: event_id
    for event_id, (_, feature_key) in _DETECTION_EVENT_FEATURES.items()
    if feature_key
}


class EntityItemSpec(NamedTuple):
    """One configurable entity within a group."""

    item_id: str
    label: str
    feature_key: str | None = None


def _detection_item_specs() -> tuple[EntityItemSpec, ...]:
    specs: list[EntityItemSpec] = []
    for event_id, event_cfg in EVENTS.items():
        if event_id == EVENT_IO:
            continue
        mapped = _DETECTION_EVENT_FEATURES.get(event_id)
        if mapped:
            label, feature_key = mapped
        else:
            label = str(event_cfg.get("label", event_id))
            feature_key = None
        specs.append(EntityItemSpec(event_id, label, feature_key))
    return tuple(specs)


ENTITY_ITEM_REGISTRY: dict[str, tuple[EntityItemSpec, ...]] = {
    ENTITY_GROUP_DETECTIONS: _detection_item_specs(),
    ENTITY_GROUP_CAMERA: (
        EntityItemSpec("camera_streams", "Camera stream entities", None),
    ),
    ENTITY_GROUP_ESSENTIAL_SYSTEM: (
        EntityItemSpec("device_uptime", "Device uptime", None),
        EntityItemSpec("reboot_count", "Reboot count", None),
        EntityItemSpec("restart_button", "Restart button", "restart"),
        EntityItemSpec("firmware_update", "Firmware update", None),
    ),
    ENTITY_GROUP_SYSTEM_DIAGNOSTICS: (
        EntityItemSpec("cpu_utilization", "CPU utilization", None),
        EntityItemSpec("memory_usage", "Memory usage", None),
        EntityItemSpec("streaming_sessions", "Streaming sessions", None),
        EntityItemSpec("streaming_clients", "Streaming clients", None),
        EntityItemSpec("notification_host", "Notification host", None),
        EntityItemSpec("notification_host_path", "Notification host path", None),
        EntityItemSpec("notification_host_port", "Notification host port", None),
        EntityItemSpec("notification_host_protocol", "Notification host protocol", None),
    ),
    ENTITY_GROUP_DAY_NIGHT: (
        EntityItemSpec("day_night_brightness", "Brightness control mode", "day_night_mode"),
        EntityItemSpec("day_night_ir_mode", "IR cut filter mode", "day_night_mode"),
        EntityItemSpec("ir_sensitivity", "IR switch sensitivity", "ir_sensitivity"),
        EntityItemSpec("ir_filter_time", "IR filter switch time", "ir_filter_time"),
    ),
    ENTITY_GROUP_SUPPLEMENT_LIGHT: (
        EntityItemSpec("supplement_light_mode", "Supplement light mode", "supplement_light_mode"),
        EntityItemSpec("white_light_time", "White light duration", "white_light_time"),
        EntityItemSpec("white_light_brightness", "White light brightness", "white_light_brightness"),
        EntityItemSpec("ir_light_brightness", "IR light brightness", "ir_light_brightness"),
        EntityItemSpec(
            "white_light_brightness_limit",
            "White light brightness limit",
            "white_light_brightness_limit",
        ),
        EntityItemSpec(
            "ir_light_brightness_limit",
            "IR light brightness limit",
            "ir_light_brightness_limit",
        ),
    ),
    ENTITY_GROUP_SIREN: (
        EntityItemSpec("siren", "Siren entity", "test_audio_alarm"),
    ),
    ENTITY_GROUP_DETECTION_SWITCHES: (
        EntityItemSpec("motion_detection", "Motion detection switch", "motion_detection"),
        EntityItemSpec("tamper_detection", "Tamper detection switch", "tamper_detection"),
        EntityItemSpec("intrusion_detection", "Intrusion detection switch", "intrusion_detection"),
        EntityItemSpec(
            "line_crossing_detection",
            "Line crossing detection switch",
            "line_crossing_detection",
        ),
        EntityItemSpec(
            "scene_change_detection",
            "Scene change detection switch",
            "scene_change_detection",
        ),
        EntityItemSpec("defocus_detection", "Defocus detection switch", "defocus_detection"),
        EntityItemSpec(
            "region_entrance_detection",
            "Region entrance detection switch",
            "region_entrance_detection",
        ),
        EntityItemSpec(
            "region_exiting_detection",
            "Region exiting detection switch",
            "region_exiting_detection",
        ),
    ),
    ENTITY_GROUP_MOTION_TUNING: (
        EntityItemSpec("motion_target_type", "Motion target type", "motion_detection"),
        EntityItemSpec("motion_sensitivity", "Motion sensitivity", "motion_sensitivity"),
        EntityItemSpec(
            "motion_start_trigger_time",
            "Motion start trigger time",
            "motion_start_trigger_time",
        ),
        EntityItemSpec(
            "motion_end_trigger_time",
            "Motion end trigger time",
            "motion_end_trigger_time",
        ),
    ),
    ENTITY_GROUP_IMAGE_ADJUSTMENT: (
        EntityItemSpec("brightness", "Brightness", "brightness"),
        EntityItemSpec("contrast", "Contrast", "contrast"),
        EntityItemSpec("saturation", "Saturation", "saturation"),
        EntityItemSpec("sharpness", "Sharpness", "sharpness"),
    ),
    ENTITY_GROUP_AUDIO_ALARM: (
        EntityItemSpec("audio_alarm_type", "Alarm audio type", "audio_alarm_type"),
        EntityItemSpec("audio_alarm_sound", "Warning sound", "audio_alarm_sound"),
        EntityItemSpec("alarm_times", "Alarm repeat count", "alarm_times"),
        EntityItemSpec("loudspeaker_volume", "Loudspeaker volume", "loudspeaker_volume"),
        EntityItemSpec("test_alarm_button", "Test alarm button", "test_audio_alarm"),
    ),
    ENTITY_GROUP_TWO_WAY_AUDIO: (
        EntityItemSpec("media_player", "Two-way audio media player", "media_player"),
        EntityItemSpec("speaker_volume", "Speaker volume", "speaker_volume"),
        EntityItemSpec("microphone_volume", "Microphone volume", "microphone_volume"),
        EntityItemSpec("noise_reduce", "Noise reduction switch", "noise_reduce"),
    ),
    ENTITY_GROUP_ALARM_IO: (
        EntityItemSpec("alarm_input_binary", "Alarm input binary sensor", "alarm_input"),
        EntityItemSpec("alarm_input_switch", "Alarm input switch", "alarm_input"),
        EntityItemSpec("alarm_output_switch", "Alarm output switch", "alarm_output"),
    ),
}

# Minimum feature keys that must pass detect_features for a group to appear in the picker.
_GROUP_FEATURE_KEYS: dict[str, tuple[str, ...]] = {
    ENTITY_GROUP_DETECTIONS: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_DETECTIONS]
        if spec.feature_key
    ) + ("alarm_input",),
    ENTITY_GROUP_DAY_NIGHT: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_DAY_NIGHT]
        if spec.feature_key
    ),
    ENTITY_GROUP_SUPPLEMENT_LIGHT: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_SUPPLEMENT_LIGHT]
        if spec.feature_key
    ),
    ENTITY_GROUP_SIREN: ("test_audio_alarm",),
    ENTITY_GROUP_DETECTION_SWITCHES: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_DETECTION_SWITCHES]
        if spec.feature_key
    ),
    ENTITY_GROUP_MOTION_TUNING: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_MOTION_TUNING]
        if spec.feature_key
    ),
    ENTITY_GROUP_IMAGE_ADJUSTMENT: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_IMAGE_ADJUSTMENT]
        if spec.feature_key
    ),
    ENTITY_GROUP_AUDIO_ALARM: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_AUDIO_ALARM]
        if spec.feature_key
    ),
    ENTITY_GROUP_TWO_WAY_AUDIO: tuple(
        spec.feature_key
        for spec in ENTITY_ITEM_REGISTRY[ENTITY_GROUP_TWO_WAY_AUDIO]
        if spec.feature_key
    ),
    ENTITY_GROUP_ALARM_IO: ("alarm_input", "alarm_output"),
}


def enrich_flow_probe(
    detected_features: dict[str, bool],
    supported_event_ids: frozenset[str],
    capabilities: dict[str, Any] | None,
) -> dict[str, bool]:
    """Merge feature probe, Event/triggers, and hardware caps for the customize picker."""
    enriched = {str(k): bool(v) for k, v in (detected_features or {}).items()}
    caps = capabilities if isinstance(capabilities, dict) else {}

    for feature_key, event_id in FEATURE_KEY_TO_EVENT_ID.items():
        if event_id in supported_event_ids:
            enriched[feature_key] = True

    if EVENT_IO in supported_event_ids or caps.get("input_ports", 0) > 0:
        enriched["alarm_input"] = True
    if caps.get("output_ports", 0) > 0:
        enriched["alarm_output"] = True

    return enriched


def build_supported_snapshot(
    detected_features: dict,
    supported_event_ids: frozenset[str],
    capabilities: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Item ids currently supported per customize category (for merge tracking)."""
    enriched = enrich_flow_probe(detected_features, supported_event_ids, capabilities)
    snapshot: dict[str, list[str]] = {}
    for group in CUSTOMIZE_FLOW_GROUPS:
        options = entity_item_options_for_flow(
            group,
            enriched,
            customize=True,
            supported_event_ids=supported_event_ids,
        )
        if options:
            snapshot[group] = [o["value"] for o in options]
    return snapshot


def merge_entry_entity_preferences(
    entry: ConfigEntry,
    detected_features: dict,
    supported_event_ids: frozenset[str],
    capabilities: dict[str, Any] | None,
) -> tuple[dict[str, list[str]], dict[str, list[str]], bool]:
    """Merge newly supported default-on items; keep user opt-ins and opt-outs."""
    profile = entry.data.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)
    if profile != PROFILE_ADVANCED:
        return {}, {}, False

    enriched = enrich_flow_probe(detected_features, supported_event_ids, capabilities)
    stored_items: dict[str, list[str]] = dict(entry.data.get(CONF_ENTITY_ITEMS) or {})
    known_supported: dict[str, list[str]] = dict(
        entry.data.get(CONF_ENTITY_KNOWN_SUPPORTED) or {}
    )
    changed = False

    for group in CUSTOMIZE_FLOW_GROUPS:
        options = entity_item_options_for_flow(
            group,
            enriched,
            customize=True,
            supported_event_ids=supported_event_ids,
        )
        supported_list = [o["value"] for o in options]
        supported_set = frozenset(supported_list)
        if not supported_set:
            continue

        old_known = frozenset(known_supported.get(group, []))
        newly_supported = supported_set - old_known

        if group in stored_items:
            enabled = {str(item) for item in stored_items[group]}
        elif group == ENTITY_GROUP_DETECTIONS:
            defaults = DEFAULT_ON_ENTITY_ITEMS.get(group, frozenset())
            enabled = {item for item in defaults if item in supported_set}
        else:
            enabled = set()

        before = frozenset(enabled)
        enabled &= supported_set

        defaults = DEFAULT_ON_ENTITY_ITEMS.get(group, frozenset())
        for item_id in newly_supported:
            if item_id in defaults:
                enabled.add(item_id)

        if enabled != before or newly_supported:
            changed = True
        stored_items[group] = sorted(enabled)
        if known_supported.get(group) != supported_list:
            changed = True
        known_supported[group] = supported_list

    return stored_items, known_supported, changed


def _item_supported_on_device(
    spec: EntityItemSpec,
    detected_features: dict,
    supported_event_ids: frozenset[str] | None = None,
) -> bool:
    if spec.feature_key == "restart":
        return bool(detected_features.get("restart", True))
    if spec.feature_key and detected_features.get(spec.feature_key):
        return True
    if supported_event_ids:
        if spec.item_id in supported_event_ids:
            return True
        if spec.feature_key:
            event_id = FEATURE_KEY_TO_EVENT_ID.get(spec.feature_key)
            if event_id and event_id in supported_event_ids:
                return True
        if spec.feature_key == "alarm_input" and EVENT_IO in supported_event_ids:
            return True
    if spec.feature_key is None:
        return True
    return False


def group_supported_on_device(group: str, detected_features: dict) -> bool:
    """Return True if this entity group can be offered for the device."""
    if group in (ENTITY_GROUP_CAMERA, ENTITY_GROUP_ESSENTIAL_SYSTEM, ENTITY_GROUP_SYSTEM_DIAGNOSTICS):
        return True
    keys = _GROUP_FEATURE_KEYS.get(group)
    if not keys:
        return False
    return any(detected_features.get(key) for key in keys)


def customize_item_specs(group: str) -> tuple[EntityItemSpec, ...]:
    """Items offered on the Advanced customize screen for one group."""
    specs = ENTITY_ITEM_REGISTRY.get(group, ())
    if group in ADVANCED_EXTRA_ENTITY_GROUPS:
        return specs
    core = BASIC_ENTITY_ITEMS.get(group)
    if core is None:
        return specs
    return tuple(spec for spec in specs if spec.item_id not in core)


def entity_item_options_for_flow(
    group: str,
    detected_features: dict,
    saved_items: list[str] | None = None,
    *,
    customize: bool = False,
    supported_event_ids: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    """Multi-select options for one group's config-flow customize step."""
    specs = customize_item_specs(group) if customize else ENTITY_ITEM_REGISTRY.get(group, ())
    event_ids = (
        supported_event_ids
        if group in (ENTITY_GROUP_DETECTIONS, ENTITY_GROUP_DETECTION_SWITCHES, ENTITY_GROUP_ALARM_IO)
        else None
    )
    options_by_id: dict[str, dict[str, str]] = {}
    for spec in specs:
        if _item_supported_on_device(spec, detected_features, event_ids):
            options_by_id[spec.item_id] = {"value": spec.item_id, "label": spec.label}
    for item_id in saved_items or ():
        item_str = str(item_id)
        if item_str in options_by_id:
            continue
        for spec in specs:
            if spec.item_id == item_str:
                options_by_id[item_str] = {"value": item_str, "label": spec.label}
                break
    return [
        options_by_id[spec.item_id]
        for spec in specs
        if spec.item_id in options_by_id
    ]


def _legacy_full_advanced_customize(
    saved_extra_groups: frozenset[str],
    saved_items: dict[str, list[str]],
) -> bool:
    """Pre-migration Advanced install: no extras map and no per-item prefs yet."""
    if saved_extra_groups:
        return False
    if not saved_items:
        return True
    return not any(saved_items.values())


def default_customize_form_values(
    detected_features: dict,
    saved_extra_groups: list[str] | frozenset[str] | None,
    saved_items: dict[str, list[str]] | None,
    *,
    supported_event_ids: frozenset[str] | None = None,
) -> dict[str, list[str]]:
    """Suggested dropdown values per customize category (reconfigure / legacy aware)."""
    saved_items = saved_items or {}
    saved_extra_set = frozenset(str(g) for g in (saved_extra_groups or ()))
    legacy_full = _legacy_full_advanced_customize(saved_extra_set, saved_items)
    values: dict[str, list[str]] = {}
    for group in CUSTOMIZE_FLOW_GROUPS:
        saved_group_items = (
            saved_items.get(group) if isinstance(saved_items.get(group), list) else None
        )
        options = entity_item_options_for_flow(
            group,
            detected_features,
            saved_group_items,
            customize=True,
            supported_event_ids=supported_event_ids,
        )
        if not options:
            continue
        option_ids = [o["value"] for o in options]
        if group in saved_items and isinstance(saved_items[group], list):
            values[group] = [str(i) for i in saved_items[group] if str(i) in option_ids]
        elif legacy_full or group in saved_extra_set:
            values[group] = option_ids
        elif group in DEFAULT_ON_ENTITY_ITEMS:
            defaults = DEFAULT_ON_ENTITY_ITEMS[group]
            values[group] = [i for i in option_ids if i in defaults]
        else:
            values[group] = []
    return values


def extract_customize_group_items(user_input: dict[str, Any], group: str) -> list[str]:
    """Read picked items from a section field or legacy flat field."""
    raw = user_input.get(group)
    if isinstance(raw, dict):
        picked = raw.get(CUSTOMIZE_SECTION_ITEMS_KEY)
        if isinstance(picked, list):
            return [str(v) for v in picked]
    if isinstance(raw, list):
        return [str(v) for v in raw]
    return []


def parse_customize_submission(
    user_input: dict[str, Any],
) -> tuple[list[str], dict[str, list[str]]]:
    """Split combined customize form into extra groups + entity item map."""
    extras: list[str] = []
    entity_items: dict[str, list[str]] = {}
    for group in CUSTOMIZE_FLOW_GROUPS:
        if group not in user_input:
            continue
        picked = extract_customize_group_items(user_input, group)
        entity_items[group] = picked
        if group in ADVANCED_EXTRA_ENTITY_GROUPS and picked:
            extras.append(group)
    return sorted(extras), entity_items


def default_entity_items_for_group(
    group: str,
    detected_features: dict,
    saved_items: list[str] | None = None,
) -> list[str]:
    """Default checked items for one group."""
    options = entity_item_options_for_flow(group, detected_features, saved_items)
    option_ids = [o["value"] for o in options]
    if saved_items:
        selected = [str(i) for i in saved_items if str(i) in option_ids]
        if selected:
            return selected
    return option_ids


def default_entity_items_for_groups(
    groups: list[str],
    detected_features: dict,
    saved: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Default item map for all selected groups."""
    saved = saved or {}
    result: dict[str, list[str]] = {}
    for group in groups:
        items = default_entity_items_for_group(
            group, detected_features, saved.get(group)
        )
        if items:
            result[group] = items
    return result


def extra_entity_group_options_for_flow(
    detected_features: dict,
    saved_extras: list[str] | frozenset[str] | None = None,
) -> list[dict[str, str]]:
    """Picker options for Advanced extras (not included in Basic)."""
    options: list[dict[str, str]] = []
    saved_set = {str(g) for g in saved_extras} if saved_extras else set()
    for group in ALL_ENTITY_GROUPS:
        if group not in ADVANCED_EXTRA_ENTITY_GROUPS:
            continue
        if group_supported_on_device(group, detected_features) or group in saved_set:
            options.append({
                "value": group,
                "label": EXTRA_ENTITY_GROUP_LABELS.get(group, ENTITY_GROUP_LABELS[group]),
            })
    return options


def stored_extra_entity_groups(stored_groups: list[str] | None) -> frozenset[str]:
    """Normalize config: legacy full lists vs extras-only storage."""
    if not isinstance(stored_groups, list) or not stored_groups:
        return frozenset()
    stored_set = frozenset(str(g) for g in stored_groups)
    if stored_set & BASIC_ENTITY_GROUPS:
        return stored_set - BASIC_ENTITY_GROUPS
    return stored_set


def entity_group_options_for_flow(
    detected_features: dict,
    saved_groups: list[str] | frozenset[str] | None = None,
) -> list[dict[str, str]]:
    """Picker options: detected groups plus any already saved on the entry."""
    options_by_value: dict[str, dict[str, str]] = {}
    for opt in supported_entity_group_options(detected_features):
        options_by_value[opt["value"]] = opt
    for group in saved_groups or ():
        group_str = str(group)
        if group_str in ENTITY_GROUP_LABELS and group_str not in options_by_value:
            options_by_value[group_str] = {
                "value": group_str,
                "label": ENTITY_GROUP_LABELS[group_str],
            }
    return [
        options_by_value[g]
        for g in ALL_ENTITY_GROUPS
        if g in options_by_value
    ]


def default_entity_groups_for_flow(
    profile: str,
    detected_features: dict,
    saved_groups: list[str] | None = None,
) -> list[str]:
    """Default multi-select values for the Advanced extras step."""
    if profile != PROFILE_ADVANCED:
        return sorted(BASIC_ENTITY_GROUPS)
    saved_extras = list(stored_extra_entity_groups(saved_groups)) if saved_groups else []
    options = extra_entity_group_options_for_flow(detected_features, saved_extras)
    option_values = {o["value"] for o in options}
    selected = [g for g in saved_extras if g in option_values]
    return selected


def supported_entity_group_options(
    detected_features: dict,
) -> list[dict[str, str]]:
    """Options for config-flow multi-select: value + label."""
    options: list[dict[str, str]] = []
    for group in ALL_ENTITY_GROUPS:
        if group_supported_on_device(group, detected_features):
            options.append({
                "value": group,
                "label": ENTITY_GROUP_LABELS[group],
            })
    return options


def default_entity_groups_for_profile(profile: str) -> list[str]:
    """Default stored groups for basic or advanced profile."""
    if profile == PROFILE_BASIC:
        return sorted(BASIC_ENTITY_GROUPS)
    return []


def get_enabled_entity_groups(entry: ConfigEntry) -> frozenset[str]:
    """Resolved entity groups for a config entry."""
    profile = entry.data.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)
    if profile == PROFILE_BASIC:
        return BASIC_ENTITY_GROUPS
    extras = stored_extra_entity_groups(entry.data.get(CONF_ENTITY_GROUPS))
    return BASIC_ENTITY_GROUPS | extras


def get_enabled_entity_items(entry: ConfigEntry, group: str) -> frozenset[str] | None:
    """Return enabled item ids for a group, or None meaning all items in the group."""
    if not entity_group_enabled(entry, group):
        return frozenset()
    profile = entry.data.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)
    if profile == PROFILE_BASIC and group in BASIC_ENTITY_ITEMS:
        return BASIC_ENTITY_ITEMS[group]
    stored = entry.data.get(CONF_ENTITY_ITEMS)
    has_item_map = isinstance(stored, dict)
    if profile == PROFILE_ADVANCED and group in BASIC_ENTITY_GROUPS:
        if not has_item_map:
            return None
        core = BASIC_ENTITY_ITEMS.get(group)
        if group in stored and isinstance(stored[group], list):
            picked = frozenset(str(item) for item in stored[group])
            if core is not None:
                return core | picked
            return picked
        if core is not None:
            return core
        return None
    if isinstance(stored, dict):
        if group in stored and isinstance(stored[group], list):
            return frozenset(str(item) for item in stored[group])
        if group not in BASIC_ENTITY_GROUPS:
            return frozenset()
    # Legacy Advanced entries: no per-item map → all items in enabled extra groups.
    return None


def entity_group_enabled(entry: ConfigEntry, group: str) -> bool:
    """True when this entity group should be created for the entry."""
    return group in get_enabled_entity_groups(entry)


def entity_item_enabled(entry: ConfigEntry, group: str, item_id: str) -> bool:
    """True when a specific item inside an enabled group should be created."""
    enabled_items = get_enabled_entity_items(entry, group)
    if enabled_items is None:
        return True
    return item_id in enabled_items


def entity_enabled(entry: ConfigEntry, group: str, item_id: str) -> bool:
    """Group and sub-item must both be enabled."""
    return entity_group_enabled(entry, group) and entity_item_enabled(entry, group, item_id)
