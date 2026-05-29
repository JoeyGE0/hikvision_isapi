"""Tests for diagnostics helpers."""

from __future__ import annotations

from custom_components.hikvision_isapi.diagnostics_snapshot import (
    _event_signature_key,
    _serialize_event,
    diagnostics_signature,
)
from custom_components.hikvision_isapi.models import EventInfo


def test_serialize_event_from_eventinfo():
    """EventInfo objects serialize without using dict .get()."""
    event = EventInfo(id="motiondetection", channel_id=1, io_port_id=0)
    assert _serialize_event(event) == {
        "id": "motiondetection",
        "channel_id": 1,
        "io_port_id": 0,
        "disabled": False,
        "is_proxy": False,
    }


def test_serialize_event_from_dict():
    """Legacy dict events still serialize."""
    event = {"id": "tamperdetection", "channel_id": 2, "disabled": True}
    assert _serialize_event(event) == {
        "id": "tamperdetection",
        "channel_id": 2,
        "io_port_id": 0,
        "disabled": True,
        "is_proxy": False,
    }


def test_diagnostics_signature_with_eventinfo_objects():
    """Signature generation must not call .get() on EventInfo dataclasses."""
    events = [
        EventInfo(id="motiondetection", channel_id=1),
        EventInfo(id="tamperdetection", channel_id=1),
    ]
    features = {"motion_detection": True, "tamper_detection": True}

    sig_a = diagnostics_signature(features, events)
    sig_b = diagnostics_signature(features, list(reversed(events)))

    assert sig_a == sig_b
    assert len(sig_a) == 16


def test_event_signature_key():
    """Event signature keys are stable for EventInfo and dict inputs."""
    assert _event_signature_key(EventInfo(id="linedetection", channel_id=3)) == "linedetection:3"
    assert _event_signature_key({"id": "fielddetection", "channel_id": 4}) == "fielddetection:4"
