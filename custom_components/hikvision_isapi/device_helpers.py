"""Single primary device per config entry (same identifier as device_registry setup)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def primary_device_identifier(device_info: dict, host: str) -> str:
    """Stable device id: serial when present, else host (matches __init__.py)."""
    sn = (device_info.get("serialNumber") or "").strip()
    return sn or host


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
        manufacturer=(device_info.get("manufacturer") or "hikvision").title(),
        model=device_info.get("model") or "Hikvision Camera",
        name=device_info.get("deviceName") or host,
        sw_version=device_info.get("firmwareVersion"),
        hw_version=hw_version,
    )


def get_primary_device_info(hass: HomeAssistant, entry: ConfigEntry) -> DeviceInfo:
    """Return cached primary DeviceInfo for entities on this config entry."""
    return hass.data[DOMAIN][entry.entry_id]["ha_device_info"]
