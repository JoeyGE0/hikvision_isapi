"""Single primary device per config entry (same identifier as device_registry setup)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

# Supplement-light API values where white-LED settings apply.
SUPPLEMENT_MODES_WHITE_ACTIVE = frozenset({"eventIntelligence", "colorVuWhiteLight"})
# Supplement-light API values where IR-LED settings apply.
SUPPLEMENT_MODES_IR_ACTIVE = frozenset({"eventIntelligence", "irLight"})

SUPPLEMENT_MODE_LABELS = {
    "eventIntelligence": "Smart",
    "colorVuWhiteLight": "White Supplement Light",
    "irLight": "IR Supplement Light",
    "close": "Off",
}


def get_supplement_light_mode(coordinator_data: dict | None) -> str | None:
    """Return raw supplementLightMode from coordinator data, if known."""
    if not coordinator_data:
        return None
    supplement = coordinator_data.get("supplement_light")
    if not isinstance(supplement, dict):
        return None
    mode = supplement.get("mode")
    return mode if isinstance(mode, str) and mode else None


def supplement_mode_label(mode: str | None) -> str:
    """Human-readable supplement light mode for error messages."""
    if not mode:
        return "unknown"
    return SUPPLEMENT_MODE_LABELS.get(mode, mode)


def supplement_mode_supports_white_light(mode: str | None) -> bool:
    """True when white-LED duration/brightness controls apply."""
    return mode in SUPPLEMENT_MODES_WHITE_ACTIVE


def supplement_mode_supports_ir_light(mode: str | None) -> bool:
    """True when IR-LED brightness controls apply."""
    return mode in SUPPLEMENT_MODES_IR_ACTIVE


def get_ircut_mode(coordinator_data: dict | None) -> str | None:
    """Return raw IrcutFilterType from coordinator data, if known."""
    if not coordinator_data:
        return None
    ircut = coordinator_data.get("ircut")
    if not isinstance(ircut, dict):
        return None
    mode = ircut.get("mode")
    return mode if isinstance(mode, str) and mode else None


def ircut_mode_is_auto(coordinator_data: dict | None) -> bool:
    """True when day/night switch sensitivity and delay settings apply."""
    return get_ircut_mode(coordinator_data) == "auto"


def ircut_mode_label(mode: str | None) -> str:
    """Human-readable IR cut mode for error messages."""
    labels = {"auto": "Auto", "day": "Day", "night": "Night"}
    if not mode:
        return "unknown"
    return labels.get(mode, mode)


def alarm_output_data_key(device_name: str, port_no: int = 1) -> str:
    """Coordinator dict key for alarm output state (matches switch entity_id slug)."""
    from homeassistant.components.switch import ENTITY_ID_FORMAT
    from homeassistant.util import slugify

    return ENTITY_ID_FORMAT.format(
        f"{slugify(device_name.lower())}_{port_no}_alarm_output"
    )


def primary_device_identifier(device_info: dict, host: str) -> str:
    """Stable device id: serial when present, else host (matches __init__.py)."""
    sn = (device_info.get("serialNumber") or "").strip()
    return sn or host


def build_configuration_url(host: str) -> str:
    """Web UI URL for the device page Visit link (matches ISAPI http access)."""
    host = host.strip()
    if host.lower().startswith(("http://", "https://")):
        return host.split("/")[0]
    normalized = host
    for prefix in ("https://", "http://"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix) :]
    return f"http://{normalized.split('/')[0].strip()}"


def build_primary_device_info(domain: str, device_info: dict, host: str) -> DeviceInfo:
    """Full DeviceInfo for the integration's main device (serial + MAC)."""
    pid = primary_device_identifier(device_info, host)
    connections: set[tuple[str, str]] = set()
    if mac := device_info.get("macAddress"):
        connections.add((dr.CONNECTION_NETWORK_MAC, mac.lower()))
    hw_version = device_info.get("hardwareVersion")
    if hw_version in ("0x0", "0", "", None):
        hw_version = None
    return DeviceInfo(
        identifiers={(domain, pid)},
        connections=connections,
        configuration_url=build_configuration_url(host),
        manufacturer=(device_info.get("manufacturer") or "hikvision").title(),
        model=device_info.get("model") or "Hikvision Camera",
        name=device_info.get("deviceName") or host,
        sw_version=device_info.get("firmwareVersion"),
        hw_version=hw_version,
    )


def get_primary_device_info(hass: HomeAssistant, entry: ConfigEntry) -> DeviceInfo:
    """Return cached primary DeviceInfo for entities on this config entry."""
    return hass.data[DOMAIN][entry.entry_id]["ha_device_info"]
