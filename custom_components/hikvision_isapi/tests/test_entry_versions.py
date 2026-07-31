"""Config entry version handling (downgrade safety + additive migrations)."""
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


def test_flow_stays_on_major_version_one():
    """A major bump breaks downgrades; additive keys must use MINOR_VERSION."""
    assert HikvisionISAPIConfigFlow.VERSION == 1
    assert HikvisionISAPIConfigFlow.VERSION == CONFIG_ENTRY_VERSION
    assert HikvisionISAPIConfigFlow.MINOR_VERSION == CONFIG_ENTRY_MINOR_VERSION


@pytest.mark.parametrize(
    ("stored_major", "expected_minor"),
    [(2, 2), (3, 3), (99, CONFIG_ENTRY_MINOR_VERSION)],
)
def test_legacy_major_maps_to_minor(stored_major, expected_minor):
    assert legacy_major_version_minor(stored_major) == expected_minor


def test_heal_rewrites_entries_written_by_old_dev_builds():
    """Entries stored as version 3 must be pulled back to 1.x before setup."""
    entry = _entry(3)
    hass = _hass([entry])

    async_heal_legacy_entry_versions(hass)

    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, version=1, minor_version=3
    )


def test_heal_leaves_current_entries_alone():
    hass = _hass([_entry(1, 3), _entry(1, 1)])

    async_heal_legacy_entry_versions(hass)

    hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_adds_profile_for_oldest_entries():
    entry = _entry(1, 1, {"host": "1.2.3.4"})
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is True

    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 1
    assert kwargs["minor_version"] == 3
    assert kwargs["data"][CONF_INTEGRATION_PROFILE] == PROFILE_ADVANCED
    assert kwargs["data"][CONF_LEGACY_FULL_INSTALL] is True


async def test_migrate_keeps_existing_choices():
    """An entry that already picked entities must not be flagged legacy."""
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
    assert kwargs["minor_version"] == 3
    assert kwargs["data"][CONF_INTEGRATION_PROFILE] == PROFILE_BASIC
    assert CONF_LEGACY_FULL_INSTALL not in kwargs["data"]


async def test_migrate_noop_when_already_current():
    entry = _entry(1, 3, {CONF_INTEGRATION_PROFILE: PROFILE_ADVANCED})
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is True
    hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_rejects_unexpected_major():
    entry = _entry(2, 1)
    hass = _hass([entry])

    assert await async_migrate_entry(hass, entry) is False
    hass.config_entries.async_update_entry.assert_not_called()
