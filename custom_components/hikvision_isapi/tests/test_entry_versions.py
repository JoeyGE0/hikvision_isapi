"""Config entry version handling (load major-3 dig entries + migrate older)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.hikvision_isapi import (
    async_heal_legacy_entry_versions,
    async_migrate_entry,
    legacy_major_version_minor,
)
from custom_components.hikvision_isapi.config_flow import HikvisionISAPIConfigFlow
from custom_components.hikvision_isapi.const import (
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    CONF_ENTITY_ITEMS,
    CONF_INTEGRATION_PROFILE,
    CONF_LEGACY_FULL_INSTALL,
    PROFILE_ADVANCED,
    PROFILE_BASIC,
)


def _entry(version: int, minor_version: int = 1, data: dict | None = None):
    return SimpleNamespace(
        title="Front Door",
        version=version,
        minor_version=minor_version,
        data=data or {},
    )


def _hass(entries):
    hass = Mock()
    hass.config_entries.async_entries.return_value = entries
    return hass


def test_flow_version_matches_dig_entries():
    """Handler major must be 3 so dig-written version-3 entries load."""
    assert HikvisionISAPIConfigFlow.VERSION == 3
    assert HikvisionISAPIConfigFlow.VERSION == CONFIG_ENTRY_VERSION
    assert HikvisionISAPIConfigFlow.MINOR_VERSION == CONFIG_ENTRY_MINOR_VERSION


def test_legacy_major_maps_to_current_minor():
    assert legacy_major_version_minor(99) == CONFIG_ENTRY_MINOR_VERSION


def test_heal_clamps_future_majors_only():
    entry = _entry(99)
    hass = _hass([entry])

    async_heal_legacy_entry_versions(hass)

    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, version=3, minor_version=1
    )


def test_heal_leaves_version_three_alone():
    """The broken state users hit — version 3 must not be rewritten away."""
    hass = _hass([_entry(3, 1), _entry(2, 1)])

    async_heal_legacy_entry_versions(hass)

    hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_promotes_v1_to_v3():
    entry = _entry(1, 1, {"host": "1.2.3.4"})
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is True

    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 3
    assert kwargs["minor_version"] == 1
    assert kwargs["data"][CONF_INTEGRATION_PROFILE] == PROFILE_ADVANCED
    assert kwargs["data"][CONF_LEGACY_FULL_INSTALL] is True


async def test_migrate_keeps_existing_choices():
    entry = _entry(
        1,
        2,
        {
            CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
            CONF_ENTITY_ITEMS: {"camera": ["main"]},
        },
    )
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is True

    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 3
    assert kwargs["data"][CONF_INTEGRATION_PROFILE] == PROFILE_BASIC
    assert CONF_LEGACY_FULL_INSTALL not in kwargs["data"]


async def test_migrate_noop_when_already_current():
    entry = _entry(3, 1, {CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED})
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is True
    hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_rejects_future_major():
    entry = _entry(4, 1)
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is False
    hass.config_entries.async_update_entry.assert_not_called()
