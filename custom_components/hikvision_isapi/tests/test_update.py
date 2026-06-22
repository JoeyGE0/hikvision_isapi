"""Tests for firmware update matching and upload error handling."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from custom_components.hikvision_isapi.api import (
    AuthenticationError,
    FirmwareUpgradeError,
    HikvisionISAPI,
)
from custom_components.hikvision_isapi.update import (
    _coordinator_data_from_firmware,
    firmware_applies_to_device,
)


class TestFirmwareAppliesToDevice:
    """applied_to must match device SKU before install is offered."""

    FIRMWARE_1063 = {
        "model": "DS-2CD1063G2-LIU(F)",
        "version": "5.8.41",
        "download_url": "https://example.com/fw.zip",
        "applied_to": (
            "Applied to: DS-2CD1063G2-LIU(F), DS-2CD1063G2-LIUF/SL, "
            "DS-2CD1063G2-LIUF/SL(2.8MM)"
        ),
        "supported_models": [
            "DS-2CD1063G2-LIUF/SL",
            "DS-2CD1383G2-LIUF/SL",
        ],
    }

    def test_matches_listed_sku(self):
        assert firmware_applies_to_device("DS-2CD1063G2-LIUF/SL", self.FIRMWARE_1063)

    def test_rejects_unlisted_supported_model(self):
        assert not firmware_applies_to_device(
            "DS-2CD1383G2-LIUF/SL", self.FIRMWARE_1063
        )

    def test_coordinator_blocks_install_for_backyard(self):
        data = _coordinator_data_from_firmware(
            self.FIRMWARE_1063,
            available=True,
            ahead_of_archive=False,
            device_model="DS-2CD1383G2-LIUF/SL",
        )
        assert data["package_compatible"] is False
        assert data["available"] is False
        assert data["download_url"] is None
        assert data["install_blocked_reason"]


@pytest.fixture
def api():
    return HikvisionISAPI("192.168.1.15", "admin", "password")


class TestFirmwareUploadErrors:
    @patch("custom_components.hikvision_isapi.api.requests.put")
    def test_put_bad_dev_type_is_not_auth_error(self, mock_put, api):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.text = """<?xml version="1.0" encoding="UTF-8"?>
      <ResponseStatus xmlns="http://www.hikvision.com/ver20/XMLSchema">
      <statusCode>4</statusCode>
      <statusString>Invalid XML Content</statusString>
      <subStatusCode>badDevType</subStatusCode>
      <description>UniNetIF_firm_upgrade failed, ret[-32], Upgrade capability mismatch.</description>
      </ResponseStatus>"""
        mock_put.return_value = response

        with pytest.raises(FirmwareUpgradeError) as err:
            api._upload_firmware_put(
                "http://192.168.1.15/ISAPI/System/updateFirmware", __file__
            )
        assert err.value.sub_status == "badDevType"

    def test_post_403_without_device_body_is_auth_error(self, api):
        response = Mock()
        response.status_code = 403
        response.ok = False
        response.text = ""
        with pytest.raises(AuthenticationError):
            api._raise_if_firmware_upload_failed(response, "POST")

    def test_post_403_bad_dev_type_in_body(self, api):
        response = Mock()
        response.status_code = 403
        response.ok = False
        response.text = (
            "<ResponseStatus><subStatusCode>badDevType</subStatusCode>"
            "<description>Upgrade capability mismatch</description></ResponseStatus>"
        )
        with pytest.raises(FirmwareUpgradeError) as err:
            api._raise_if_firmware_upload_failed(response, "POST")
        assert err.value.sub_status == "badDevType"
