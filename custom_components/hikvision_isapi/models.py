"""Data models for Hikvision ISAPI."""
from __future__ import annotations
from dataclasses import dataclass, field


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
    active_state: str = None  # "active" or "inactive" - indicates if event is starting or ending


@dataclass
class MutexIssue:
    """Holds mutually exclusive event checking info."""

    event_id: str
    channels: list = field(default_factory=list)  # List of channel IDs that have conflicting events enabled


@dataclass
class EventInfo:
    """Holds event info of Hikvision device."""

    id: str
    channel_id: int
    io_port_id: int = 0
    unique_id: str = None
    url: str = None  # URL to fetch the event status (enabled/disabled)
    disabled: bool = False
    is_proxy: bool = False  # True if the event comes from device connected via NVR

