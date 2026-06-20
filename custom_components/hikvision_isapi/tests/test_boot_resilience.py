"""Tests for ISAPI boot-time resilience (retries + webhook self-heal).

Reproduces the user's failure mode:
  - Event/triggers HTTP 500 during camera boot
  - motiondetection webhooks arrive but binary_sensor entity missing
  - reconfigure fixed it once ISAPI was stable

These tests prove the fix without blindly creating entities on unsupported cameras.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests

from custom_components.hikvision_isapi import _discover_isapi_capabilities
from custom_components.hikvision_isapi.api import HikvisionISAPI
from custom_components.hikvision_isapi.const import ISAPI_BOOT_RETRY_DELAYS
from custom_components.hikvision_isapi.models import AlertInfo, EventInfo
from custom_components.hikvision_isapi.notifications import (
    EventNotificationsView,
    _entity_missing_reload_pending,
    _last_entity_missing_reload,
)


@pytest.fixture
def api():
    return HikvisionISAPI("192.168.1.14", "admin", "password")


@pytest.fixture
def mock_hass():
    hass = Mock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.async_create_task = Mock()
    return hass


class TestTransientErrorDetection:
    """Prove 500/timeout triggers retry; 403/404 does not."""

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_500_on_probe_sets_unstable_flag(self, mock_get, api):
        response = Mock()
        response.status_code = 500
        mock_get.return_value = response

        assert api._test_endpoint_exists("/ISAPI/Event/triggers/motiondetection-1") is False
        assert api.isapi_boot_unstable is True

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_403_on_probe_does_not_set_unstable_flag(self, mock_get, api):
        response = Mock()
        response.status_code = 403
        mock_get.return_value = response

        assert api._test_endpoint_exists("/ISAPI/Event/triggers/regionEntrance") is False
        assert api.isapi_boot_unstable is False

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_timeout_on_probe_sets_unstable_flag(self, mock_get, api):
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        assert api._test_endpoint_exists("/ISAPI/System/capabilities") is False
        assert api.isapi_boot_unstable is True

    @patch.object(HikvisionISAPI, "_build_supported_events_fallback", return_value=[])
    @patch.object(HikvisionISAPI, "_get")
    def test_event_triggers_500_sets_unstable_flag(self, mock_get, _fallback, api):
        err = requests.exceptions.HTTPError("500")
        err.response = Mock(status_code=500)
        mock_get.side_effect = err

        events = api.get_supported_events()

        assert events == []
        assert api.isapi_boot_unstable is True


class TestDiscoveryRetry:
    """Prove setup retries on transient ISAPI errors and stops when stable."""

    @pytest.mark.asyncio
    async def test_retries_until_isapi_stable_then_returns_motion(self, mock_hass, api):
        """Simulates boot: first two attempts 500, third succeeds with motion."""
        call_count = {"n": 0}

        def detect_features():
            call_count["n"] += 1
            if call_count["n"] < 3:
                api.isapi_boot_unstable = True
                return {}
            api.isapi_boot_unstable = False
            return {"motion_detection": True, "restart": True}

        def get_supported_events():
            if call_count["n"] < 3:
                api.isapi_boot_unstable = True
                return []
            from custom_components.hikvision_isapi.models import EventInfo

            return [
                EventInfo(id="motiondetection", channel_id=1, io_port_id=0, disabled=False)
            ]

        api.detect_features = detect_features
        api.get_supported_events = get_supported_events

        with patch(
            "custom_components.hikvision_isapi.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            features, events = await _discover_isapi_capabilities(
                mock_hass, api, "192.168.1.14"
            )

        assert features.get("motion_detection") is True
        assert len(events) == 1
        assert events[0].id == "motiondetection"
        assert mock_sleep.await_count == len(ISAPI_BOOT_RETRY_DELAYS)

    @pytest.mark.asyncio
    async def test_no_retry_when_first_attempt_stable(self, mock_hass, api):
        api.detect_features = Mock(
            return_value={"motion_detection": True, "restart": True}
        )
        api.get_supported_events = Mock(return_value=[])

        with patch(
            "custom_components.hikvision_isapi.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            features, _events = await _discover_isapi_capabilities(
                mock_hass, api, "192.168.1.14"
            )

        assert features.get("motion_detection") is True
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_motion_created_when_probes_consistently_fail(self, mock_hass, api):
        """Unsupported / still-down camera: no fake motion after all retries."""

        def detect_features():
            api.isapi_boot_unstable = True
            return {"restart": True}  # only always-available restart button

        api.detect_features = detect_features
        api.get_supported_events = Mock(return_value=[])

        with patch(
            "custom_components.hikvision_isapi.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            features, events = await _discover_isapi_capabilities(
                mock_hass, api, "192.168.1.14"
            )

        assert features.get("motion_detection") is None
        assert events == []


class TestBinarySensorGating:
    """Prove entities only created when ISAPI confirms support."""

    @pytest.mark.asyncio
    async def test_skips_motion_when_not_detected_and_not_in_triggers(self):
        from custom_components.hikvision_isapi.binary_sensor import async_setup_entry

        added: list = []

        def async_add_entities(entities):
            added.extend(entities)

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.1.14"}

        hass = Mock()
        domain_data = {
            "coordinator": Mock(last_update_success=True),
            "api": Mock(),
            "host": "192.168.1.14",
            "device_info": {"deviceName": "Driveway", "serialNumber": "SN1"},
            "cameras": [{"id": 1, "name": "Driveway", "serial_no": "SN1"}],
            "capabilities": {"is_nvr": False},
            "supported_events": [],
            "detected_features": {"restart": True},
            "nvr_device_identifier": "192.168.1.14",
        }
        hass.data = {"hikvision_isapi": {"test": domain_data}}
        domain_data["coordinator"].hass = hass

        await async_setup_entry(hass, entry, async_add_entities)

        motion_entities = [
            e for e in added if getattr(e.event, "id", None) == "motiondetection"
        ]
        assert motion_entities == []

    @pytest.mark.asyncio
    async def test_creates_motion_when_supported_events_lists_it(self):
        from custom_components.hikvision_isapi.binary_sensor import async_setup_entry

        added: list = []

        def async_add_entities(entities):
            added.extend(entities)

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {"host": "192.168.1.14"}

        hass = Mock()
        domain_data = {
            "coordinator": Mock(last_update_success=True),
            "api": Mock(),
            "host": "192.168.1.14",
            "device_info": {"deviceName": "Driveway", "serialNumber": "SN1"},
            "cameras": [{"id": 1, "name": "Driveway", "serial_no": "SN1"}],
            "capabilities": {"is_nvr": False},
            "supported_events": [
                EventInfo(
                    id="motiondetection",
                    channel_id=1,
                    io_port_id=0,
                    disabled=False,
                )
            ],
            "detected_features": {"restart": True},
            "nvr_device_identifier": "192.168.1.14",
        }
        hass.data = {"hikvision_isapi": {"test": domain_data}}
        domain_data["coordinator"].hass = hass

        await async_setup_entry(hass, entry, async_add_entities)

        motion_entities = [
            e for e in added if getattr(e.event, "id", None) == "motiondetection"
        ]
        assert len(motion_entities) == 1
        assert motion_entities[0]._attr_unique_id == "driveway_1_motiondetection"


class TestWebhookSelfHeal:
    """Prove missing entity + incoming webhook schedules config reload."""

    def setup_method(self):
        _entity_missing_reload_pending.clear()
        _last_entity_missing_reload.clear()

    def test_schedules_reload_when_webhook_proves_event_exists(self):
        view = EventNotificationsView(Mock())
        view.hass = Mock()
        view.hass.async_create_task = Mock()

        entry = Mock()
        entry.entry_id = "driveway_entry"

        scheduled = []

        def capture_later(hass, delay, callback):
            scheduled.append(delay)
            callback(0)

        with patch(
            "custom_components.hikvision_isapi.notifications.async_call_later",
            side_effect=capture_later,
        ):
            view._maybe_schedule_missing_entity_reload(entry, "motiondetection", "Driveway")

        assert scheduled == [30.0]
        view.hass.async_create_task.assert_called_once()

    def test_throttles_reload_to_once_per_interval(self):
        view = EventNotificationsView(Mock())
        view.hass = Mock()
        entry = Mock()
        entry.entry_id = "driveway_entry"
        _last_entity_missing_reload["driveway_entry"] = __import__("time").monotonic()

        with patch(
            "custom_components.hikvision_isapi.notifications.async_call_later",
        ) as mock_later:
            view._maybe_schedule_missing_entity_reload(entry, "motiondetection", "Driveway")

        mock_later.assert_not_called()


class TestUserScenarioEndToEnd:
    """Driveway + Front Door scenario from the user's logs."""

    @pytest.mark.asyncio
    async def test_flaky_boot_then_webhook_self_heal_path(self, mock_hass, api):
        """Attempt 1: 500 (no motion entity). Attempt 3: motion confirmed. Webhook reload as backup."""
        attempt = {"n": 0}

        def detect_features():
            attempt["n"] += 1
            if attempt["n"] == 1:
                api.isapi_boot_unstable = True
                return {}
            api.isapi_boot_unstable = False
            return {"motion_detection": True, "restart": True}

        def get_supported_events():
            if attempt["n"] == 1:
                return []
            return [
                EventInfo(
                    id="motiondetection", channel_id=1, io_port_id=0, disabled=False
                )
            ]

        api.detect_features = detect_features
        api.get_supported_events = get_supported_events

        with patch(
            "custom_components.hikvision_isapi.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            features, events = await _discover_isapi_capabilities(
                mock_hass, api, "192.168.1.14"
            )

        assert features.get("motion_detection") is True
        assert any(e.id == "motiondetection" for e in events)

        # unique_id from user logs
        assert events[0].channel_id == 1

        # If setup still missed entity, webhook self-heal fires reload
        view = EventNotificationsView(Mock())
        view.hass = Mock()
        view.hass.async_create_task = Mock()
        entry = Mock(entry_id="driveway")

        with patch(
            "custom_components.hikvision_isapi.notifications.async_call_later",
            side_effect=lambda _h, _d, cb: cb(0),
        ):
            view._maybe_schedule_missing_entity_reload(
                entry, "motiondetection", "Driveway"
            )

        view.hass.async_create_task.assert_called_once()
