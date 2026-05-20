"""Tests for Hikvision ISAPI config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hikvision_isapi.config_flow import HikvisionISAPIConfigFlow
from custom_components.hikvision_isapi.const import (
    CONF_ALARM_SERVER_HOST,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SET_ALARM_SERVER,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DOMAIN,
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
    }
    entry.entry_id = "test_entry_id"
    return entry


class TestConfigFlow:
    """Test cases for config flow."""

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_success(self, mock_get, flow):
        """Test successful user step."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = ""
        mock_get.return_value = response

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = Mock()
        flow.async_create_entry = Mock(return_value={"type": FlowResultType.CREATE_ENTRY})

        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
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
        mock_source_ip.return_value = "192.168.1.1"
        flow._get_reconfigure_entry = Mock(return_value=mock_entry)
        flow._reconfigure_entry = mock_entry
        flow.source = SOURCE_RECONFIGURE

        result = await flow.async_step_reconfigure(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert "data_schema" in result
        mock_source_ip.assert_not_called()

    @patch("custom_components.hikvision_isapi.config_flow.async_get_source_ip", new_callable=AsyncMock)
    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_reconfigure_step_updates_entry(
        self, mock_get, mock_source_ip, flow, mock_entry
    ):
        """Reconfigure updates the existing entry and reloads."""
        mock_source_ip.return_value = "192.168.1.1"
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = ""
        mock_get.return_value = response

        flow._get_reconfigure_entry = Mock(return_value=mock_entry)
        flow._reconfigure_entry = mock_entry
        flow.source = SOURCE_RECONFIGURE
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = Mock()
        flow.async_update_reload_and_abort = Mock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure({
            CONF_HOST: "192.168.1.15",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password_after_reset",
            CONF_VERIFY_SSL: True,
            CONF_UPDATE_INTERVAL: 30,
            CONF_SET_ALARM_SERVER: True,
            CONF_ALARM_SERVER_HOST: "http://192.168.1.1:8123",
        })

        assert result["type"] == FlowResultType.ABORT
        flow.async_update_reload_and_abort.assert_called_once()
