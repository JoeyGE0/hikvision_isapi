"""Tests for Hikvision ISAPI config flow."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, AsyncMock
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hikvision_isapi.config_flow import HikvisionISAPIConfigFlow
from custom_components.hikvision_isapi.const import DOMAIN


@pytest.fixture
def flow():
    """Create a config flow instance for testing."""
    hass = Mock(spec=HomeAssistant)
    flow = HikvisionISAPIConfigFlow()
    flow.hass = hass
    flow._async_current_entries = Mock(return_value=[])
    flow._async_abort_entries_match = Mock()
    return flow


class TestConfigFlow:
    """Test cases for config flow."""

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_success(self, mock_get, flow):
        """Test successful user step."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        mock_get.return_value = response
        
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = Mock()
        flow.async_create_entry = AsyncMock(return_value=Mock())
        
        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
            "update_interval": 30,
        })
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        mock_get.assert_called_once()

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_invalid_auth(self, mock_get, flow):
        """Test user step with invalid authentication."""
        response = Mock()
        response.status_code = 401
        mock_get.return_value = response
        
        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "wrong",
        })
        
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result
        assert result["errors"]["base"] == "invalid_auth"

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_cannot_connect(self, mock_get, flow):
        """Test user step when cannot connect."""
        response = Mock()
        response.status_code = 404
        mock_get.return_value = response
        
        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
        })
        
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result
        assert result["errors"]["base"] == "cannot_connect"

    @patch("custom_components.hikvision_isapi.config_flow.requests.get")
    async def test_user_step_timeout(self, mock_get, flow):
        """Test user step with timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = await flow.async_step_user({
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
        })
        
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result
        assert result["errors"]["base"] == "timeout"

