"""Tests for Hikvision ISAPI coordinator."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import timedelta

from custom_components.hikvision_isapi.coordinator import HikvisionDataUpdateCoordinator
from custom_components.hikvision_isapi.api import HikvisionISAPI, AuthenticationError


@pytest.fixture
def mock_api():
    """Create a mock API instance."""
    api = Mock(spec=HikvisionISAPI)
    api.get_ircut_filter = Mock(return_value={})
    api.get_supplement_light = Mock(return_value={})
    api.get_two_way_audio = Mock(return_value={})
    api.get_motion_detection = Mock(return_value={})
    api.get_tamper_detection = Mock(return_value={})
    api.get_field_detection = Mock(return_value={})
    api.get_line_detection = Mock(return_value={})
    api.get_scene_change_detection = Mock(return_value={})
    api.get_region_entrance = Mock(return_value={})
    api.get_region_exiting = Mock(return_value={})
    api.get_white_light_time = Mock(return_value={})
    api.get_system_status = Mock(return_value={})
    api.get_streaming_status = Mock(return_value={})
    api.get_alarm_input = Mock(return_value={})
    api.get_alarm_output = Mock(return_value={})
    return api


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = Mock()
    entry.data = {"host": "192.168.1.100", "update_interval": 30}
    entry.entry_id = "test_entry"
    return entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return hass


class TestCoordinator:
    """Test cases for HikvisionDataUpdateCoordinator."""

    @pytest.mark.asyncio
    async def test_update_data_success(self, mock_hass, mock_entry, mock_api):
        """Test successful data update."""
        coordinator = HikvisionDataUpdateCoordinator(
            mock_hass, mock_entry, mock_api, 30
        )
        
        result = await coordinator._async_update_data()
        
        assert isinstance(result, dict)
        assert "ircut" in result
        assert "motion" in result
        assert "tamper" in result

    @pytest.mark.asyncio
    async def test_update_data_authentication_error(self, mock_hass, mock_entry, mock_api):
        """Test data update with authentication error."""
        mock_api.get_ircut_filter.side_effect = AuthenticationError("Auth failed")
        coordinator = HikvisionDataUpdateCoordinator(
            mock_hass, mock_entry, mock_api, 30
        )
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_error_recovery(self, mock_hass, mock_entry, mock_api):
        """Test error recovery with exponential backoff."""
        coordinator = HikvisionDataUpdateCoordinator(
            mock_hass, mock_entry, mock_api, 30
        )
        
        # Simulate errors
        mock_api.get_ircut_filter.side_effect = Exception("Connection error")
        
        # First error
        try:
            await coordinator._async_update_data()
        except Exception:
            pass
        
        assert coordinator._consecutive_errors == 1
        
        # Second error - should increase update interval
        try:
            await coordinator._async_update_data()
        except Exception:
            pass
        
        assert coordinator._consecutive_errors == 2
        assert coordinator.update_interval.total_seconds() > 30

