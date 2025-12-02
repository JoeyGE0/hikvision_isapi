"""Tests for Hikvision ISAPI API helper."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from custom_components.hikvision_isapi.api import HikvisionISAPI, AuthenticationError


@pytest.fixture
def api():
    """Create a HikvisionISAPI instance for testing."""
    return HikvisionISAPI("192.168.1.100", "admin", "password")


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = Mock()
    response.status_code = 200
    response.ok = True
    response.text = '<?xml version="1.0" encoding="UTF-8"?><ResponseStatus version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema"><requestURL>/ISAPI/System/deviceInfo</requestURL><statusCode>1</statusCode><statusString>OK</statusString></ResponseStatus>'
    return response


class TestHikvisionISAPI:
    """Test cases for HikvisionISAPI class."""

    def test_init(self):
        """Test API initialization."""
        api = HikvisionISAPI("192.168.1.100", "admin", "password")
        assert api.host == "192.168.1.100"
        assert api.username == "admin"
        assert api.password == "password"
        assert api.channel == 1

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_get_success(self, mock_get, api, mock_response):
        """Test successful GET request."""
        mock_get.return_value = mock_response
        
        result = api._get("/ISAPI/System/deviceInfo")
        
        assert result is not None
        mock_get.assert_called_once()

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_get_authentication_error_401(self, mock_get, api):
        """Test authentication error (401)."""
        response = Mock()
        response.status_code = 401
        mock_get.return_value = response
        
        with pytest.raises(AuthenticationError):
            api._get("/ISAPI/System/deviceInfo")

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_get_authentication_error_403(self, mock_get, api):
        """Test authentication error (403)."""
        response = Mock()
        response.status_code = 403
        mock_get.return_value = response
        
        with pytest.raises(AuthenticationError):
            api._get("/ISAPI/System/deviceInfo")

    @patch("custom_components.hikvision_isapi.api.requests.get")
    def test_get_device_info(self, mock_get, api):
        """Test get_device_info method."""
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <DeviceInfo version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
            <deviceName>Test Camera</deviceName>
            <deviceID>12345</deviceID>
            <model>DS-2CD2387G3</model>
            <serialNumber>ABC123</serialNumber>
            <firmwareVersion>V5.8.10</firmwareVersion>
            <hardwareVersion>0x0</hardwareVersion>
            <macAddress>84:94:59:E4:AA:9D</macAddress>
        </DeviceInfo>'''
        mock_get.return_value = response
        
        result = api.get_device_info()
        
        assert result["deviceName"] == "Test Camera"
        assert result["model"] == "DS-2CD2387G3"
        assert result["serialNumber"] == "ABC123"
        assert result["firmwareVersion"] == "V5.8.10"
        assert result["macAddress"] == "84:94:59:E4:AA:9D"

    @patch("custom_components.hikvision_isapi.api.requests.get")
    @patch("custom_components.hikvision_isapi.api.requests.put")
    def test_set_motion_detection(self, mock_put, mock_get, api):
        """Test set_motion_detection method."""
        get_response = Mock()
        get_response.status_code = 200
        get_response.ok = True
        get_response.text = '<?xml version="1.0"?><MotionDetection><enabled>false</enabled></MotionDetection>'
        mock_get.return_value = get_response
        
        put_response = Mock()
        put_response.status_code = 200
        put_response.ok = True
        mock_put.return_value = put_response
        
        result = api.set_motion_detection(True)
        
        assert result is True
        mock_get.assert_called_once()
        mock_put.assert_called_once()

