"""Basic vs Advanced entity profiles for config flow and platform setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENTITY_GROUPS,
    CONF_INTEGRATION_PROFILE,
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
    PROFILE_ADVANCED,
    PROFILE_BASIC,
)

# Human-readable labels for the config-flow multi-select (translation keys in en.json).
ENTITY_GROUP_LABELS: dict[str, str] = {
    ENTITY_GROUP_DETECTIONS: "Event detections (binary sensors)",
    ENTITY_GROUP_CAMERA: "Camera streams",
    ENTITY_GROUP_ESSENTIAL_SYSTEM: "Essentials (uptime, restart, firmware)",
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

BASIC_ENTITY_GROUPS: frozenset[str] = frozenset({
    ENTITY_GROUP_DETECTIONS,
    ENTITY_GROUP_CAMERA,
    ENTITY_GROUP_ESSENTIAL_SYSTEM,
    ENTITY_GROUP_DAY_NIGHT,
    ENTITY_GROUP_SUPPLEMENT_LIGHT,
    ENTITY_GROUP_SIREN,
})

# Matches today's default exposure when hardware supports everything.
ADVANCED_DEFAULT_ENTITY_GROUPS: frozenset[str] = frozenset(ALL_ENTITY_GROUPS)

# Minimum feature keys that must pass detect_features for a group to appear in the picker.
_GROUP_FEATURE_KEYS: dict[str, tuple[str, ...]] = {
    ENTITY_GROUP_DETECTIONS: (
        "motion_detection",
        "tamper_detection",
        "intrusion_detection",
        "line_crossing_detection",
        "scene_change_detection",
        "defocus_detection",
        "region_entrance_detection",
        "region_exiting_detection",
        "alarm_input",
    ),
    ENTITY_GROUP_DAY_NIGHT: (
        "day_night_mode",
        "ir_sensitivity",
        "ir_filter_time",
    ),
    ENTITY_GROUP_SUPPLEMENT_LIGHT: (
        "supplement_light_mode",
        "white_light_time",
        "white_light_brightness",
        "ir_light_brightness",
        "white_light_brightness_limit",
        "ir_light_brightness_limit",
    ),
    ENTITY_GROUP_SIREN: ("test_audio_alarm",),
    ENTITY_GROUP_DETECTION_SWITCHES: (
        "motion_detection",
        "tamper_detection",
        "intrusion_detection",
        "line_crossing_detection",
        "scene_change_detection",
        "defocus_detection",
        "region_entrance_detection",
        "region_exiting_detection",
    ),
    ENTITY_GROUP_MOTION_TUNING: (
        "motion_detection",
        "motion_sensitivity",
        "motion_start_trigger_time",
        "motion_end_trigger_time",
    ),
    ENTITY_GROUP_IMAGE_ADJUSTMENT: (
        "brightness",
        "contrast",
        "saturation",
        "sharpness",
    ),
    ENTITY_GROUP_AUDIO_ALARM: (
        "audio_alarm_type",
        "audio_alarm_sound",
        "alarm_times",
        "loudspeaker_volume",
        "test_audio_alarm",
    ),
    ENTITY_GROUP_TWO_WAY_AUDIO: (
        "media_player",
        "speaker_volume",
        "microphone_volume",
        "noise_reduce",
    ),
    ENTITY_GROUP_ALARM_IO: ("alarm_input", "alarm_output"),
}


def group_supported_on_device(group: str, detected_features: dict) -> bool:
    """Return True if this entity group can be offered for the device."""
    if group == ENTITY_GROUP_CAMERA:
        return True
    if group == ENTITY_GROUP_ESSENTIAL_SYSTEM:
        return True
    if group == ENTITY_GROUP_SYSTEM_DIAGNOSTICS:
        return True
    keys = _GROUP_FEATURE_KEYS.get(group)
    if not keys:
        return False
    return any(detected_features.get(key) for key in keys)


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
    """Default selected groups for basic or advanced profile."""
    if profile == PROFILE_BASIC:
        return sorted(BASIC_ENTITY_GROUPS)
    return sorted(ADVANCED_DEFAULT_ENTITY_GROUPS)


def get_enabled_entity_groups(entry: ConfigEntry) -> frozenset[str]:
    """Resolved entity groups for a config entry."""
    profile = entry.data.get(CONF_INTEGRATION_PROFILE, PROFILE_ADVANCED)
    if profile == PROFILE_BASIC:
        return BASIC_ENTITY_GROUPS
    stored = entry.data.get(CONF_ENTITY_GROUPS)
    if isinstance(stored, list) and stored:
        return frozenset(str(g) for g in stored)
    return ADVANCED_DEFAULT_ENTITY_GROUPS


def entity_group_enabled(entry: ConfigEntry, group: str) -> bool:
    """True when this entity group should be created for the entry."""
    return group in get_enabled_entity_groups(entry)
