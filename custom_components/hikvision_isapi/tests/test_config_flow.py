"""Tests for Hikvision ISAPI config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hikvision_isapi.config_flow import (
    HikvisionISAPIConfigFlow,
    _apply_suggested_values,
    _coerce_config_entry_for_form,
    _fallback_apply_suggested_values,
    _filter_suggested_values,
    _reconfigure_schema,
)
import voluptuous as vol
from custom_components.hikvision_isapi.const import (
    CONF_ALARM_SERVER_HOST,
    CONF_ENTITY_KNOWN_SUPPORTED,
    CONF_HOST,
    CONF_INTEGRATION_PROFILE,
    CONF_PASSWORD,
    CONF_SET_ALARM_SERVER,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    PROFILE_BASIC,
    PROFILE_ADVANCED,
)


@pytest.fixture
def flow():
    """Create a config flow instance for testing."""
    hass = Mock(spec=HomeAssistant)
    flow = HikvisionISAPIConfigFlow()
    flow.hass = hass
    flow._async_current_entries = Mock(return_value=[])
    flow._async_abort_entries_match = Mock()
    return flow


@pytest.fixture
def mock_entry():
    """Config entry used for reconfigure/reauth tests."""
    entry = Mock(spec=config_entries.ConfigEntry)
    entry.data = {
        CONF_HOST: "192.168.1.15",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "old_password",
        CONF_VERIFY_SSL: True,
        CONF_UPDATE_INTERVAL: 30,
        CONF_SET_ALARM_SERVER: True,
        CONF_ALARM_SERVER_HOST: "http://192.168.1.1:8123",
        CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
    }
    entry.entry_id = "test_entry_id"
    entry.title = "Backyard Camera"
    return entry


class TestConfigFlowHelpers:
    """Tests for config flow schema helpers."""

    def test_filter_suggested_excludes_password(self):
        """Password must not be sent as a suggested value."""
        schema = _reconfigure_schema()
        suggested = {
            CONF_HOST: "192.168.1.15",
            CONF_PASSWORD: "secret",
            CONF_USERNAME: "admin",
        }
        filtered = _filter_suggested_values(schema, suggested)
        assert CONF_PASSWORD not in filtered
        assert filtered[CONF_HOST] == "192.168.1.15"

    def test_apply_suggested_values_fallback(self, flow):
        """Fallback suggested values work without HA helper."""
        schema = _reconfigure_schema()
        result = _apply_suggested_values(
            flow,
            schema,
            {CONF_HOST: "10.0.0.5", CONF_USERNAME: "admin"},
        )
        assert result is not None

    def test_fallback_apply_suggested_with_string_marker_description(self):
        """Markers with non-dict description must not crash (HA 2026.5 reconfigure 500)."""
        schema = vol.Schema({
            vol.Required("host", description="legacy-string-desc"): str,
        })
        result = _fallback_apply_suggested_values(schema, {"host": "192.168.1.15"})
        assert result is not None

    def test_coerce_config_entry_excludes_password(self):
        """Password must never be passed as a suggested form value."""
        data = _coerce_config_entry_for_form({
            CONF_HOST: "192.168.1.15",
            CONF_PASSWORD: "secret",
            CONF_USERNAME: "admin",
            CONF_VERIFY_SSL: "true",
        })
        assert CONF_PASSWORD not in data
        assert data[CONF_VERIFY_SSL] is True


class TestConfigFlow:
    """Test cases for config flow."""

    @patch("custom_components.hikvision_isapi.config_flow.async_get_source_ip", new_callable=AsyncMock)
    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_success(self, mock_get, mock_source_ip, flow):
        """Test successful user step (Basic profile)."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = ""
        mock_get.return_value = response
        mock_source_ip.return_value = "192.168.1.1"
        flow.hass.async_add_executor_job = AsyncMock(return_value={})

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = Mock()
        flow.async_create_entry = Mock(return_value={"type": FlowResultType.CREATE_ENTRY})

        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
            CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
        })

        assert result["type"] == FlowResultType.CREATE_ENTRY
        mock_get.assert_called_once()

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_invalid_auth(self, mock_get, flow):
        """Test user step with invalid authentication."""
        response = Mock()
        response.status_code = 401
        response.ok = False
        mock_get.return_value = response

        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "wrong",
        })

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_cannot_connect(self, mock_get, flow):
        """Test user step when cannot connect."""
        response = Mock()
        response.status_code = 404
        response.ok = False
        mock_get.return_value = response

        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
        })

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_timeout(self, mock_get, flow):
        """Test user step with timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
        })

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "timeout"

    @patch("custom_components.hikvision_isapi.config_flow.async_get_source_ip", new_callable=AsyncMock)
    async def test_reconfigure_step_shows_form(self, mock_source_ip, flow, mock_entry):
        """Reconfigure must load the form without calling network (no 500)."""
        flow._get_reconfigure_entry = Mock(return_value=mock_entry)

        result = await flow.async_step_reconfigure(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert "data_schema" in result
        assert result.get("description_placeholders") == {"name": mock_entry.title}
        mock_source_ip.assert_not_called()

    @patch("custom_components.hikvision_isapi.config_flow.async_get_source_ip", new_callable=AsyncMock)
    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_reconfigure_step_updates_entry(
        self, mock_get, mock_source_ip, flow, mock_entry
    ):
        """Reconfigure updates the existing entry and reloads."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = ""
        mock_get.return_value = response

        flow._get_reconfigure_entry = Mock(return_value=mock_entry)
        flow.async_update_reload_and_abort = Mock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure({
            CONF_HOST: "192.168.1.15",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password_after_reset",
            CONF_VERIFY_SSL: True,
            CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
            CONF_UPDATE_INTERVAL: 30,
            CONF_SET_ALARM_SERVER: True,
            CONF_ALARM_SERVER_HOST: "http://192.168.1.1:8123",
        })

        assert result["type"] == FlowResultType.ABORT
        flow.async_update_reload_and_abort.assert_called_once()

    @patch("custom_components.hikvision_isapi.config_flow.async_get_source_ip", new_callable=AsyncMock)
    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_reconfigure_blank_password_keeps_stored(
        self, mock_get, mock_source_ip, flow, mock_entry
    ):
        """Reconfigure with empty password field uses stored credentials."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = ""
        mock_get.return_value = response

        flow._get_reconfigure_entry = Mock(return_value=mock_entry)
        flow.async_update_reload_and_abort = Mock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure({
            CONF_HOST: "192.168.1.15",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
            CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
            CONF_UPDATE_INTERVAL: 30,
            CONF_SET_ALARM_SERVER: True,
            CONF_ALARM_SERVER_HOST: "http://192.168.1.1:8123",
        })

        assert result["type"] == FlowResultType.ABORT
        call_kwargs = flow.async_update_reload_and_abort.call_args.kwargs
        assert call_kwargs["data_updates"][CONF_PASSWORD] == "old_password"


class TestEntityCustomizeCoverage:
    """Registry + flow probe must list every integration entity."""

    def test_alarm_io_from_capabilities(self):
        from custom_components.hikvision_isapi.const import ENTITY_GROUP_ALARM_IO, EVENT_IO
        from custom_components.hikvision_isapi.entity_profiles import (
            CUSTOMIZE_FLOW_GROUPS,
            customize_item_specs,
            enrich_flow_probe,
            entity_item_options_for_flow,
        )

        enriched = enrich_flow_probe({}, frozenset(), {"input_ports": 1, "output_ports": 1})
        opts = entity_item_options_for_flow(
            ENTITY_GROUP_ALARM_IO, enriched, customize=True, supported_event_ids=frozenset()
        )
        assert {o["value"] for o in opts} == {
            "alarm_input_binary", "alarm_input_switch", "alarm_output_switch",
        }

    def test_detection_switch_from_event_trigger(self):
        from custom_components.hikvision_isapi.entity_profiles import (
            enrich_flow_probe,
            entity_item_options_for_flow,
        )

        enriched = enrich_flow_probe({}, frozenset({"linedetection"}), {})
        opts = entity_item_options_for_flow(
            "detection_switches",
            enriched,
            customize=True,
            supported_event_ids=frozenset({"linedetection"}),
        )
        assert "line_crossing_detection" in {o["value"] for o in opts}

    def test_full_probe_lists_all_customize_items(self):
        from custom_components.hikvision_isapi.const import EVENT_IO
        from custom_components.hikvision_isapi.entity_profiles import (
            CUSTOMIZE_FLOW_GROUPS,
            customize_item_specs,
            enrich_flow_probe,
            entity_item_options_for_flow,
        )

        all_features = {k: True for k in (
            "motion_detection", "tamper_detection", "intrusion_detection",
            "line_crossing_detection", "scene_change_detection", "region_entrance_detection",
            "region_exiting_detection", "defocus_detection", "day_night_mode", "ir_sensitivity",
            "ir_filter_time", "white_light_time", "white_light_brightness", "ir_light_brightness",
            "white_light_brightness_limit", "ir_light_brightness_limit", "supplement_light_mode",
            "test_audio_alarm", "audio_alarm_type", "audio_alarm_sound", "alarm_times",
            "loudspeaker_volume", "media_player", "microphone_volume",
            "noise_reduce", "brightness", "contrast", "saturation", "sharpness",
            "motion_sensitivity", "motion_start_trigger_time", "motion_end_trigger_time",
            "restart", "alarm_input", "alarm_output",
        )}
        events = frozenset({
            "motiondetection", "tamperdetection", "videoloss", "fielddetection", "linedetection",
            "scenechangedetection", "regionentrance", "regionexiting", "defocus", EVENT_IO,
        })
        enriched = enrich_flow_probe(all_features, events, {"input_ports": 1, "output_ports": 1})
        for group in CUSTOMIZE_FLOW_GROUPS:
            expected = {s.item_id for s in customize_item_specs(group)}
            got = {
                o["value"]
                for o in entity_item_options_for_flow(
                    group, enriched, customize=True, supported_event_ids=events
                )
            }
            assert got == expected, f"{group}: missing {expected - got}"

    def test_merge_adds_new_default_detection_only(self):
        from custom_components.hikvision_isapi.const import ENTITY_GROUP_DETECTIONS
        from custom_components.hikvision_isapi.entity_profiles import (
            merge_entry_entity_preferences,
        )

        entry = Mock(spec=config_entries.ConfigEntry)
        entry.data = {
            CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED,
            CONF_ENTITY_ITEMS: {
                ENTITY_GROUP_DETECTIONS: ["motiondetection", "tamperdetection", "videoloss"],
            },
            CONF_ENTITY_KNOWN_SUPPORTED: {
                ENTITY_GROUP_DETECTIONS: ["motiondetection", "tamperdetection", "videoloss"],
            },
        }
        features = {"line_crossing_detection": True}
        events = frozenset({"motiondetection", "tamperdetection", "videoloss", "linedetection"})
        items, known, changed = merge_entry_entity_preferences(entry, features, events, {})
        assert changed
        assert "linedetection" not in items[ENTITY_GROUP_DETECTIONS]
        assert "linedetection" in known[ENTITY_GROUP_DETECTIONS]

    def test_merge_auto_enables_new_default_detection(self):
        from custom_components.hikvision_isapi.const import ENTITY_GROUP_DETECTIONS
        from custom_components.hikvision_isapi.entity_profiles import (
            merge_entry_entity_preferences,
        )

        entry = Mock(spec=config_entries.ConfigEntry)
        entry.data = {
            CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED,
            CONF_ENTITY_ITEMS: {ENTITY_GROUP_DETECTIONS: ["tamperdetection"]},
            CONF_ENTITY_KNOWN_SUPPORTED: {
                ENTITY_GROUP_DETECTIONS: ["tamperdetection"],
            },
        }
        features = {"motion_detection": True}
        events = frozenset({"motiondetection", "tamperdetection", "videoloss"})
        items, _, changed = merge_entry_entity_preferences(entry, features, events, {})
        assert changed
        assert "motiondetection" in items[ENTITY_GROUP_DETECTIONS]

    def test_legacy_full_install_enables_all_groups(self):
        from custom_components.hikvision_isapi.const import (
            CONF_LEGACY_FULL_INSTALL,
            ENTITY_GROUP_ALARM_IO,
            ENTITY_GROUP_IMAGE_ADJUSTMENT,
        )
        from custom_components.hikvision_isapi.entity_profiles import (
            get_enabled_entity_groups,
            get_enabled_entity_items,
            is_legacy_full_install,
        )

        entry = Mock(spec=config_entries.ConfigEntry)
        entry.data = {
            CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED,
            CONF_LEGACY_FULL_INSTALL: True,
        }
        assert is_legacy_full_install(entry)
        groups = get_enabled_entity_groups(entry)
        assert ENTITY_GROUP_IMAGE_ADJUSTMENT in groups
        assert ENTITY_GROUP_ALARM_IO in groups
        assert get_enabled_entity_items(entry, ENTITY_GROUP_IMAGE_ADJUSTMENT) is None
        from custom_components.hikvision_isapi.const import ENTITY_GROUP_DETECTIONS
        from custom_components.hikvision_isapi.entity_profiles import (
            merge_entry_entity_preferences,
        )

        entry = Mock(spec=config_entries.ConfigEntry)
        entry.data = {
            CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED,
            CONF_ENTITY_ITEMS: {ENTITY_GROUP_DETECTIONS: ["tamperdetection"]},
            CONF_ENTITY_KNOWN_SUPPORTED: {
                ENTITY_GROUP_DETECTIONS: [
                    "motiondetection", "tamperdetection", "videoloss",
                ],
            },
        }
        items, _, changed = merge_entry_entity_preferences(
            entry, {"motion_detection": True}, frozenset({
                "motiondetection", "tamperdetection", "videoloss",
            }), {},
        )
        assert not changed
        assert "motiondetection" not in items[ENTITY_GROUP_DETECTIONS]
