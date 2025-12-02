"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import pytest
from unittest.mock import Mock


@pytest.fixture(autouse=True)
def disable_ssl_warnings():
    """Disable SSL warnings in tests."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

