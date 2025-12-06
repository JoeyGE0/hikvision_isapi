"""Data models for Hikvision ISAPI."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AlertInfo:
    """Holds camera event notification info."""

    channel_id: int
    io_port_id: int = 0
    event_id: str = ""
    device_serial_no: str = None
    mac: str = ""
    region_id: int = 0
    detection_target: str = None


@dataclass
class EventInfo:
    """Holds event info of Hikvision device."""

    id: str
    channel_id: int
    io_port_id: int = 0
    unique_id: str = None
    url: str = None  # URL to fetch the event status (enabled/disabled)
    disabled: bool = False

