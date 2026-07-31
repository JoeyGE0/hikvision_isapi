"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import copy
import logging
from typing import Any
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.components.network import async_get_source_ip
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import SelectSelectorMode

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    CONF_ENTITY_GROUPS,
    CONF_ENTITY_ITEMS,
    CONF_ENTITY_KNOWN_SUPPORTED,
    CONF_LEGACY_FULL_INSTALL,
    CONF_HOST,
    CONF_INTEGRATION_PROFILE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    CONF_SET_ALARM_SERVER,
    CONF_ALARM_SERVER_HOST,
    CONF_VERIFY_SSL,
    CUSTOMIZE_SECTION_ITEMS_KEY,
    PROFILE_ADVANCED,
    PROFILE_BASIC,
    RTSP_PORT_FORCED,
)
from .api import HikvisionISAPI, _extract_error_message, _normalize_host
from .entity_profiles import (
    CUSTOMIZE_FLOW_GROUPS,
    build_supported_snapshot,
    default_customize_form_values,
    enrich_flow_probe,
    entity_item_options_for_flow,
    entry_has_advanced_entity_setup,
    entry_needs_advanced_profile_heal,
    parse_customize_submission,
    stored_extra_entity_groups,
)

_XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"

# Never pre-fill password in UI suggestions (HA security + avoids config flow crashes).
_SENSITIVE_SUGGEST_KEYS = frozenset({CONF_PASSWORD})


def _parse_rtsp_port(value: Any) -> int | None:
    """Parse optional RTSP port from form input; None if empty."""
    if value is None or value == "":
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        port = int(str(value).strip())
    except (ValueError, TypeError) as err:
        raise vol.Invalid("invalid_rtsp_port") from err
    if not 1 <= port <= 65535:
        raise vol.Invalid("invalid_rtsp_port")
    return port


def _validate_rtsp_port_field(value: Any, errors: dict[str, str]) -> int | None:
    """Validate RTSP port from form; record errors and return parsed port or None."""
    try:
        return _parse_rtsp_port(value)
    except vol.Invalid:
        errors[RTSP_PORT_FORCED] = "invalid_rtsp_port"
        return None


def _rtsp_port_form_schema() -> type:
    """Serializable optional RTSP port field (empty string = unset)."""
    return str


def _parse_device_info_response(response: requests.Response, fallback_host: str) -> tuple[str, str | None]:
    """Return (device_name, serial_number) from a deviceInfo HTTP response."""
    device_name = fallback_host
    serial_number = None
    if not response.ok:
        return device_name, serial_number
    try:
        root = ET.fromstring(response.text)
        name_elem = root.find(f".//{_XML_NS}deviceName")
        if name_elem is not None and name_elem.text:
            device_name = name_elem.text.strip()
        serial_elem = root.find(f".//{_XML_NS}serialNumber")
        if serial_elem is not None and serial_elem.text:
            serial_number = serial_elem.text.strip()
    except ET.ParseError:
        pass
    return device_name, serial_number


def _schema_field_names(data_schema: vol.Schema) -> set[str]:
    """Return config field names from a voluptuous schema."""
    names: set[str] = set()
    for key in data_schema.schema:
        if isinstance(key, vol.Marker):
            names.add(key.schema)
    return names


def _as_bool(value: Any, default: bool = False) -> bool:
    """Coerce config entry values for boolean form fields."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if value is None:
        return default
    return bool(value)


def _coerce_config_entry_for_form(entry_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize stored config entry data for config flow suggested values."""
    coerced: dict[str, Any] = {
        CONF_HOST: str(entry_data.get(CONF_HOST, "")),
        CONF_USERNAME: str(entry_data.get(CONF_USERNAME, "admin")),
        CONF_VERIFY_SSL: _as_bool(entry_data.get(CONF_VERIFY_SSL), True),
        CONF_UPDATE_INTERVAL: int(entry_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)),
        CONF_SET_ALARM_SERVER: _as_bool(entry_data.get(CONF_SET_ALARM_SERVER), True),
        CONF_ALARM_SERVER_HOST: str(entry_data.get(CONF_ALARM_SERVER_HOST, "")),
        CONF_INTEGRATION_PROFILE: str(
            entry_data.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)
        ),
    }
    if entry_data.get(CONF_LEGACY_FULL_INSTALL):
        coerced[CONF_INTEGRATION_PROFILE] = PROFILE_ADVANCED
    if RTSP_PORT_FORCED in entry_data and entry_data[RTSP_PORT_FORCED] is not None:
        coerced[RTSP_PORT_FORCED] = str(entry_data[RTSP_PORT_FORCED])
    return coerced


def _form_values_with_submission(
    entry_data: dict[str, Any],
    user_input: dict[str, Any] | None,
    default_alarm_server: str | None = None,
) -> dict[str, Any]:
    """Form values from stored config, overlaid with the last submitted input.

    Redisplaying a form after a validation error must not discard what the user
    just chose (e.g. switching Setup mode to Advanced), otherwise the field snaps
    back to the stored value on every failed attempt.
    """
    values = _coerce_config_entry_for_form(entry_data)
    for key, value in (user_input or {}).items():
        if key in _SENSITIVE_SUGGEST_KEYS:
            continue
        values[key] = value
    # Apply after overlay so an empty submitted alarm host still gets a usable default.
    if default_alarm_server and not str(values.get(CONF_ALARM_SERVER_HOST) or "").strip():
        values[CONF_ALARM_SERVER_HOST] = default_alarm_server
    return values


def _alarm_host_needs_default(
    entry_data: dict[str, Any], user_input: dict[str, Any] | None
) -> bool:
    """True when the reconfigure form would show an empty alarm-server host."""
    if user_input is not None and CONF_ALARM_SERVER_HOST in user_input:
        return not str(user_input.get(CONF_ALARM_SERVER_HOST) or "").strip()
    return not str(entry_data.get(CONF_ALARM_SERVER_HOST) or "").strip()


def _filter_suggested_values(
    data_schema: vol.Schema, suggested: dict[str, Any] | None
) -> dict[str, Any]:
    """Keep only keys that exist in the schema; drop secrets and None RTSP."""
    if not suggested:
        return {}
    allowed = _schema_field_names(data_schema)
    filtered: dict[str, Any] = {}
    for key, value in suggested.items():
        if key not in allowed or key in _SENSITIVE_SUGGEST_KEYS:
            continue
        if key == RTSP_PORT_FORCED and value in (None, ""):
            continue
        filtered[key] = value
    return filtered


def _fallback_apply_suggested_values(
    data_schema: vol.Schema, suggested: dict[str, Any]
) -> vol.Schema:
    """Fallback when add_suggested_values_to_schema is unavailable or fails."""
    schema: dict = {}
    for key, value in data_schema.schema.items():
        if not isinstance(key, vol.Marker):
            continue
        new_key = copy.copy(key)
        field_suggested = suggested.get(key.schema)
        if isinstance(value, data_entry_flow.section) and isinstance(field_suggested, dict):
            new_value = data_entry_flow.section(
                _fallback_apply_suggested_values(value.schema, field_suggested),
                value.options,
            )
            schema[new_key] = new_value
            continue
        if field_suggested is not None:
            existing = new_key.description
            if isinstance(existing, dict):
                new_key.description = {**existing, "suggested_value": field_suggested}
            else:
                new_key.description = {"suggested_value": field_suggested}
        schema[new_key] = value
    return vol.Schema(schema)


def _apply_suggested_values(
    handler: config_entries.ConfigFlow,
    data_schema: vol.Schema,
    suggested: dict[str, Any] | None,
) -> vol.Schema:
    """Apply suggested values with HA helper when available, else safe fallback."""
    suggested = _filter_suggested_values(data_schema, suggested)
    if not suggested:
        return data_schema
    if hasattr(handler, "add_suggested_values_to_schema"):
        try:
            return handler.add_suggested_values_to_schema(data_schema, suggested)
        except Exception:
            _LOGGER.exception("add_suggested_values_to_schema failed, using fallback schema")
    return _fallback_apply_suggested_values(data_schema, suggested)


def get_basic_schema(default_host: str | None = None):
    """Get basic schema for initial setup (legacy helper for tests)."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=default_host or ""): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_INTEGRATION_PROFILE, default=PROFILE_BASIC): vol.In(
            (PROFILE_BASIC, PROFILE_ADVANCED)
        ),
    })


def get_advanced_schema(default_alarm_server: str | None = None, set_alarm_server: bool = True):
    """Get advanced options schema (initial setup advanced step)."""
    schema: dict = {
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
        vol.Required(CONF_SET_ALARM_SERVER, default=set_alarm_server): bool,
        vol.Optional(RTSP_PORT_FORCED, default=""): _rtsp_port_form_schema(),
    }
    if set_alarm_server:
        schema[vol.Required(CONF_ALARM_SERVER_HOST, default=default_alarm_server or "")] = str
    return vol.Schema(schema)


def _reconfigure_schema() -> vol.Schema:
    """Static reconfigure schema (must not change shape between form loads)."""
    return vol.Schema({
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_VERIFY_SSL): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_INTEGRATION_PROFILE): vol.In((PROFILE_BASIC, PROFILE_ADVANCED)),
        vol.Optional(CONF_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
        vol.Required(CONF_SET_ALARM_SERVER): bool,
        vol.Optional(CONF_ALARM_SERVER_HOST): str,
        vol.Optional(RTSP_PORT_FORCED, default=""): _rtsp_port_form_schema(),
    })


class HikvisionISAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    def __init__(self) -> None:
        """Initialize flow handler."""
        self._discovered_host: str | None = None
        self._reconfigure_entry: config_entries.ConfigEntry | None = None
        self._detected_features: dict[str, bool] = {}
        self._supported_event_ids: frozenset[str] = frozenset()
        self._device_capabilities: dict[str, Any] = {}

    async def _async_probe_detected_features(
        self, host: str, username: str, password: str, verify_ssl: bool
    ) -> dict[str, bool]:
        """Run feature + event detection during setup (for entity customize picker)."""
        api = HikvisionISAPI(host, username, password, verify_ssl=verify_ssl)
        self._supported_event_ids = frozenset()
        self._device_capabilities = {}
        try:
            await self.hass.async_add_executor_job(api.get_device_info)
            self._device_capabilities = (
                dict(api.capabilities) if isinstance(api.capabilities, dict) else {}
            )
            features = await self.hass.async_add_executor_job(api.detect_features)
            if isinstance(features, dict):
                api.detected_features = features
            if hasattr(api, "get_supported_events"):
                try:
                    supported = await self.hass.async_add_executor_job(
                        api.get_supported_events
                    )
                    self._supported_event_ids = frozenset(
                        str(e.id) for e in (supported or []) if getattr(e, "id", None)
                    )
                except Exception:
                    _LOGGER.debug(
                        "Supported-events probe failed during config flow for %s",
                        host,
                        exc_info=True,
                    )
            return features if isinstance(features, dict) else {}
        except Exception:
            _LOGGER.exception("Feature probe during config flow failed for %s", host)
            return {}

    def _integration_profile_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Required(CONF_INTEGRATION_PROFILE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=PROFILE_BASIC, label="Basic"
                        ),
                        selector.SelectOptionDict(
                            value=PROFILE_ADVANCED, label="Advanced"
                        ),
                    ],
                    translation_key="integration_profile",
                )
            ),
        })

    def _entity_customize_schema(self, detected_features: dict) -> vol.Schema:
        saved_extras = self.context.get("saved_extra_groups") or []
        saved_items = self.context.get("default_entity_items") or {}
        if not isinstance(saved_items, dict):
            saved_items = {}
        supported_event_ids = (
            self._supported_event_ids
            or self.context.get("supported_event_ids")
            or frozenset()
        )
        capabilities = (
            self._device_capabilities
            or self.context.get("device_capabilities")
            or {}
        )
        enriched = enrich_flow_probe(
            detected_features, supported_event_ids, capabilities
        )
        suggested = default_customize_form_values(
            enriched,
            saved_extras,
            saved_items,
            supported_event_ids=supported_event_ids,
            legacy_full_install=bool(self.context.get("legacy_full_install")),
        )
        schema_dict: dict = {}
        section_suggested: dict[str, dict[str, list[str]]] = {}
        for group in CUSTOMIZE_FLOW_GROUPS:
            options = entity_item_options_for_flow(
                group,
                enriched,
                suggested.get(group),
                customize=True,
                supported_event_ids=supported_event_ids,
            )
            if not options:
                continue
            group_items = suggested.get(group, [])
            section_suggested[group] = {CUSTOMIZE_SECTION_ITEMS_KEY: group_items}
            schema_dict[vol.Required(group)] = data_entry_flow.section(
                vol.Schema({
                    vol.Optional(CUSTOMIZE_SECTION_ITEMS_KEY): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=o["value"], label=o["label"]
                                )
                                for o in options
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }),
                {"collapsed": not bool(group_items)},
            )
        return _apply_suggested_values(
            self, vol.Schema(schema_dict), section_suggested
        )

    def _flow_supported_snapshot(self) -> dict[str, list[str]]:
        return build_supported_snapshot(
            self._detected_features,
            self._supported_event_ids,
            self._device_capabilities,
        )

    async def _async_finish_reconfigure_preserve_entities(self) -> ConfigFlowResult:
        """Apply reconfigure credentials/options without changing entity preferences."""
        reconfigure_input = self.context.get("reconfigure_input")
        if not reconfigure_input:
            return self.async_abort(reason="no_basic_data")
        entry = self._reconfigure_entry or self._get_reconfigure_entry()
        entry_data = self._build_entry_data(reconfigure_input)
        title = self.context.get("reconfigure_device_name", entry.title)
        return self.async_update_reload_and_abort(
            entry,
            data_updates=entry_data,
            title=title,
        )

    def _merge_unoffered_entity_prefs(
        self,
        entry: config_entries.ConfigEntry,
        groups: list[str],
        entity_items: dict[str, list[str]],
        known_supported: dict[str, list[str]] | None = None,
    ) -> tuple[list[str], dict[str, list[str]], dict[str, list[str]] | None]:
        """Keep saved picks for categories the customize screen could not offer.

        A failed or partial capability probe (camera rebooting, 401/403 while
        detecting) shrinks the customize form. Categories missing from the form
        must keep their stored selections instead of being silently cleared.
        """
        stored_items = entry.data.get(CONF_ENTITY_ITEMS)
        merged_known = dict(known_supported) if isinstance(known_supported, dict) else known_supported
        if not isinstance(stored_items, dict):
            return groups, entity_items, merged_known

        merged_items = dict(entity_items)
        for group, picked in stored_items.items():
            if group not in merged_items and isinstance(picked, list):
                merged_items[group] = list(picked)

        merged_groups = set(groups)
        for group in stored_extra_entity_groups(entry.data.get(CONF_ENTITY_GROUPS)):
            if group not in entity_items and merged_items.get(group):
                merged_groups.add(group)

        stored_known = entry.data.get(CONF_ENTITY_KNOWN_SUPPORTED)
        if isinstance(stored_known, dict):
            if not isinstance(merged_known, dict):
                merged_known = {}
            for group, items in stored_known.items():
                if group not in merged_known and isinstance(items, list):
                    merged_known[group] = list(items)

        if merged_items != entity_items or merged_groups != set(groups):
            _LOGGER.warning(
                "Customize form for %s did not offer every category; keeping stored "
                "selections for %s",
                entry.data.get(CONF_HOST),
                ", ".join(sorted(set(merged_items) - set(entity_items))) or "none",
            )
        return sorted(merged_groups), merged_items, merged_known

    async def _async_finish_advanced_setup(
        self,
        groups: list[str],
        entity_items: dict[str, list[str]],
        known_supported: dict[str, list[str]] | None = None,
    ) -> ConfigFlowResult:
        """Create or update an Advanced entry (Basic core + optional extras)."""
        if reconfigure_input := self.context.get("reconfigure_input"):
            entry = self._reconfigure_entry or self._get_reconfigure_entry()
            groups, entity_items, known_supported = self._merge_unoffered_entity_prefs(
                entry, groups, entity_items, known_supported
            )
            merged = {
                **reconfigure_input,
                CONF_ENTITY_GROUPS: groups,
                CONF_ENTITY_ITEMS: entity_items,
                CONF_ENTITY_KNOWN_SUPPORTED: (
                    known_supported
                    if known_supported is not None
                    else self._flow_supported_snapshot()
                ),
            }
            entry_data = self._build_entry_data(merged)
            title = self.context.get("reconfigure_device_name", entry.title)
            return self.async_update_reload_and_abort(
                entry,
                data_updates=entry_data,
                title=title,
            )

        basic_data = self.context.get("user_input", {})
        advanced = self.context.get("advanced_options", {})
        if not basic_data:
            return self.async_abort(reason="no_basic_data")
        finalized = self._finalize_advanced_entry_data(
            {}, groups, entity_items, known_supported
        )
        if not groups and not entity_items:
            finalized[CONF_LEGACY_FULL_INSTALL] = True
        entry_data = {
            **basic_data,
            **advanced,
            **finalized,
        }
        device_name = basic_data.get("device_name", basic_data.get(CONF_HOST, "Hikvision"))
        return await self._async_create_entry_from_context(
            entry_data,
            device_name,
            entry_data[CONF_HOST],
            entry_data.get(CONF_VERIFY_SSL, True),
        )

    def _finalize_advanced_entry_data(
        self,
        base_data: dict[str, Any],
        groups: list[str],
        entity_items: dict[str, list[str]],
        known_supported: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        data = dict(base_data)
        data[CONF_INTEGRATION_PROFILE] = PROFILE_ADVANCED
        data[CONF_ENTITY_GROUPS] = groups
        data[CONF_ENTITY_ITEMS] = entity_items
        data[CONF_ENTITY_KNOWN_SUPPORTED] = (
            known_supported if known_supported is not None else self._flow_supported_snapshot()
        )
        data[CONF_LEGACY_FULL_INSTALL] = False
        return data

    async def _async_create_entry_from_context(
        self, entry_data: dict[str, Any], device_name: str, host: str, verify_ssl: bool
    ) -> ConfigFlowResult:
        """Set unique_id and create the config entry."""
        _, _, serial_number = await self._async_validate_connection(
            host,
            entry_data[CONF_USERNAME],
            entry_data[CONF_PASSWORD],
            verify_ssl,
        )
        unique_id = serial_number or self.unique_id or host
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        title = entry_data.pop("device_name", device_name)
        return self.async_create_entry(title=title, data=entry_data)

    async def _async_default_alarm_server(self) -> str:
        """Home Assistant URL for camera event notifications."""
        try:
            local_ip = await async_get_source_ip(self.hass)
            return f"http://{local_ip}:8123"
        except Exception:
            _LOGGER.debug("Could not resolve source IP for alarm server default")
            return "http://homeassistant.local:8123"

    async def _async_get_user_schema(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> vol.Schema:
        """Schema for new setup (user + DHCP discovery)."""
        suggested: dict[str, Any] = dict(user_input or {})
        if self._discovered_host and CONF_HOST not in suggested:
            suggested[CONF_HOST] = self._discovered_host
        suggested.setdefault(CONF_USERNAME, "admin")
        suggested.setdefault(CONF_VERIFY_SSL, True)
        suggested.setdefault(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_VERIFY_SSL): bool,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_INTEGRATION_PROFILE): vol.In(
                (PROFILE_BASIC, PROFILE_ADVANCED)
            ),
        })
        return _apply_suggested_values(self, schema, suggested)

    async def _async_validate_connection(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool,
    ) -> tuple[dict[str, str], str, str | None]:
        """Test ISAPI deviceInfo; return (errors, device_name, serial_number)."""
        errors: dict[str, str] = {}
        device_name = host
        serial_number = None

        try:
            host = _normalize_host(host)
            url = f"http://{host}/ISAPI/System/deviceInfo"
            auth = HTTPDigestAuth(username, password)
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(
                    url,
                    auth=auth,
                    verify=verify_ssl,
                    timeout=15,
                )
            )
            device_name, serial_number = _parse_device_info_response(response, host)

            if response.status_code in (401, 403):
                errors["base"] = "invalid_auth"
            elif response.status_code == 404:
                errors["base"] = "cannot_connect"
            elif not response.ok:
                error_msg = _extract_error_message(response)
                if error_msg and error_msg != "OK":
                    _LOGGER.warning("Connection test failed for %s: %s", host, error_msg)
                errors["base"] = "cannot_connect"

        except requests.exceptions.Timeout:
            errors["base"] = "timeout"
        except requests.exceptions.ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during config flow for %s", host)
            errors["base"] = "unknown"

        return errors, device_name, serial_number

    def _build_entry_data(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Normalize reconfigure/reauth form into config entry data."""
        entry = self._reconfigure_entry
        stored = dict(entry.data) if entry else {}

        host = user_input[CONF_HOST].strip()
        password = user_input.get(CONF_PASSWORD, "")
        if not password and entry:
            password = stored.get(CONF_PASSWORD, "")

        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_USERNAME: user_input[CONF_USERNAME].strip(),
            CONF_PASSWORD: password,
            CONF_VERIFY_SSL: user_input.get(
                CONF_VERIFY_SSL, stored.get(CONF_VERIFY_SSL, True)
            ),
            CONF_UPDATE_INTERVAL: user_input.get(
                CONF_UPDATE_INTERVAL,
                stored.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ),
            CONF_SET_ALARM_SERVER: user_input.get(
                CONF_SET_ALARM_SERVER, stored.get(CONF_SET_ALARM_SERVER, True)
            ),
        }
        if data[CONF_SET_ALARM_SERVER]:
            alarm_host = user_input.get(CONF_ALARM_SERVER_HOST)
            if alarm_host is None:
                alarm_host = stored.get(CONF_ALARM_SERVER_HOST, "")
            data[CONF_ALARM_SERVER_HOST] = str(alarm_host).strip()
        elif entry:
            data[CONF_ALARM_SERVER_HOST] = stored.get(CONF_ALARM_SERVER_HOST, "")

        if RTSP_PORT_FORCED in user_input:
            port = _parse_rtsp_port(user_input.get(RTSP_PORT_FORCED))
            if port is not None:
                data[RTSP_PORT_FORCED] = port
        elif RTSP_PORT_FORCED in stored:
            data[RTSP_PORT_FORCED] = stored[RTSP_PORT_FORCED]

        if CONF_INTEGRATION_PROFILE in user_input:
            profile = user_input[CONF_INTEGRATION_PROFILE]
        elif entry:
            profile = stored.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)
        else:
            profile = PROFILE_BASIC
        data[CONF_INTEGRATION_PROFILE] = profile

        if profile == PROFILE_ADVANCED:
            groups = user_input.get(CONF_ENTITY_GROUPS)
            if isinstance(groups, list):
                data[CONF_ENTITY_GROUPS] = sorted(stored_extra_entity_groups(groups))
            elif entry:
                data[CONF_ENTITY_GROUPS] = sorted(
                    stored_extra_entity_groups(stored.get(CONF_ENTITY_GROUPS))
                )
            else:
                data[CONF_ENTITY_GROUPS] = []

            entity_items = user_input.get(CONF_ENTITY_ITEMS)
            if isinstance(entity_items, dict):
                data[CONF_ENTITY_ITEMS] = entity_items
            elif entry:
                saved_items = stored.get(CONF_ENTITY_ITEMS)
                if isinstance(saved_items, dict):
                    data[CONF_ENTITY_ITEMS] = saved_items

            known = user_input.get(CONF_ENTITY_KNOWN_SUPPORTED)
            if isinstance(known, dict):
                data[CONF_ENTITY_KNOWN_SUPPORTED] = known
            elif entry:
                saved_known = stored.get(CONF_ENTITY_KNOWN_SUPPORTED)
                if isinstance(saved_known, dict):
                    data[CONF_ENTITY_KNOWN_SUPPORTED] = saved_known

            if CONF_ENTITY_ITEMS in user_input:
                data[CONF_LEGACY_FULL_INSTALL] = False
            elif CONF_LEGACY_FULL_INSTALL in user_input:
                data[CONF_LEGACY_FULL_INSTALL] = bool(user_input[CONF_LEGACY_FULL_INSTALL])
            elif entry and stored.get(CONF_LEGACY_FULL_INSTALL):
                data[CONF_LEGACY_FULL_INSTALL] = True
        elif entry and stored.get(CONF_LEGACY_FULL_INSTALL):
            data[CONF_LEGACY_FULL_INSTALL] = False

        return data

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an existing entry (host, credentials, advanced options)."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        self._reconfigure_entry = entry

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "") or entry.data.get(CONF_PASSWORD, "")

            if not host:
                errors[CONF_HOST] = "host_required"
            if not username:
                errors[CONF_USERNAME] = "username_required"
            if not password:
                errors[CONF_PASSWORD] = "password_required"
            if (
                user_input.get(CONF_SET_ALARM_SERVER, True)
                and not user_input.get(CONF_ALARM_SERVER_HOST, "").strip()
            ):
                errors[CONF_ALARM_SERVER_HOST] = "alarm_server_required"

            _validate_rtsp_port_field(user_input.get(RTSP_PORT_FORCED), errors)

            if not errors:
                verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
                errors, device_name, serial_number = await self._async_validate_connection(
                    host, username, password, verify_ssl
                )
                if not errors:
                    profile = user_input.get(
                        CONF_INTEGRATION_PROFILE,
                        entry.data.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC),
                    )
                    if (
                        profile == PROFILE_BASIC
                        and entry_has_advanced_entity_setup(entry)
                    ):
                        errors[CONF_INTEGRATION_PROFILE] = "cannot_downgrade_to_basic"
                    else:
                        self.context["reconfigure_input"] = user_input
                        self.context["reconfigure_device_name"] = device_name
                    if not errors and profile == PROFILE_ADVANCED:
                        self._detected_features = await self._async_probe_detected_features(
                            host, username, password, verify_ssl
                        )
                        self.context["saved_extra_groups"] = list(
                            stored_extra_entity_groups(
                                entry.data.get(CONF_ENTITY_GROUPS)
                            )
                        )
                        saved_items = entry.data.get(CONF_ENTITY_ITEMS)
                        self.context["default_entity_items"] = (
                            saved_items if isinstance(saved_items, dict) else {}
                        )
                        self.context["legacy_full_install"] = bool(
                            entry.data.get(CONF_LEGACY_FULL_INSTALL)
                        )
                        return await self.async_step_entity_customize()
                    if not errors:
                        entry_data = self._build_entry_data(user_input)
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates=entry_data,
                            title=device_name,
                        )

        try:
            base_schema = _reconfigure_schema()
            entry_data = dict(entry.data)
            default_alarm = None
            if _alarm_host_needs_default(entry_data, user_input):
                default_alarm = await self._async_default_alarm_server()
            suggested = _form_values_with_submission(
                entry_data,
                user_input,
                default_alarm,
            )
            data_schema = _apply_suggested_values(self, base_schema, suggested)
        except Exception:
            _LOGGER.exception("Failed to build reconfigure form schema")
            errors["base"] = "unknown"
            data_schema = _reconfigure_schema()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Re-authenticate after invalid credentials (e.g. camera factory reset)."""
        self._reconfigure_entry = self._get_reauth_entry()
        return await self._async_reauth_form(None, {})

    async def _async_reauth_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> ConfigFlowResult:
        """Show and process the reauth credentials form."""
        entry = self._reconfigure_entry or self._get_reauth_entry()
        self._reconfigure_entry = entry

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")

            if not host:
                errors[CONF_HOST] = "host_required"
            if not username:
                errors[CONF_USERNAME] = "username_required"
            if not password:
                errors[CONF_PASSWORD] = "password_required"

            if not errors:
                verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
                errors, _, _ = await self._async_validate_connection(
                    host, username, password, verify_ssl
                )
                if not errors:
                    # HA reauth must only update auth fields — never profile/entity prefs.
                    # See: developers.home-assistant.io config flow reauthentication.
                    data_updates: dict[str, Any] = {
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_VERIFY_SSL: verify_ssl,
                    }
                    if entry_needs_advanced_profile_heal(entry):
                        data_updates[CONF_INTEGRATION_PROFILE] = PROFILE_ADVANCED
                        _LOGGER.warning(
                            "Reauth healed %s back to Advanced (Basic profile with "
                            "leftover Advanced entity prefs)",
                            host,
                        )
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=data_updates,
                    )

        # Reauth uses a smaller schema (credentials + host only)
        base_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_VERIFY_SSL): bool,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        try:
            suggested = _form_values_with_submission(dict(entry.data), user_input)
            data_schema = _apply_suggested_values(self, base_schema, suggested)
        except Exception:
            _LOGGER.exception("Failed to build reauth form schema")
            errors["base"] = "unknown"
            data_schema = base_schema
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth entry point used by newer Home Assistant versions."""
        self._reconfigure_entry = self._get_reauth_entry()
        return await self._async_reauth_form(user_input, {})

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        _LOGGER.info(
            "DHCP discovery triggered: IP=%s, MAC=%s, Hostname=%s",
            discovery_info.ip,
            discovery_info.macaddress,
            discovery_info.hostname,
        )

        host = discovery_info.ip
        macaddress = discovery_info.macaddress

        if not host or not macaddress:
            return self.async_abort(reason="invalid_discovery_info")

        for existing_entry in self._async_current_entries():
            if existing_entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        mac_address = format_mac(macaddress)
        await self.async_set_unique_id(mac_address)
        try:
            self._abort_if_unique_id_configured()
        except data_entry_flow.AbortFlow:
            return self.async_abort(reason="already_configured")

        device_name = discovery_info.hostname or host
        try:
            url = f"http://{host}/ISAPI/System/deviceInfo"
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(url, verify=False, timeout=3)
            )
            parsed_name, _ = _parse_device_info_response(response, host)
            if parsed_name:
                device_name = parsed_name
        except Exception:
            pass

        self._discovered_host = host
        self.context.update({
            "discovered_host": host,
            "discovered_device_name": device_name,
            "title_placeholders": {"name": device_name or host},
        })

        return await self.async_step_user(None)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup only (not reconfigure/reauth)."""
        if self.source == SOURCE_REAUTH:
            return await self._async_reauth_form(user_input, {})

        errors: dict[str, str] = {}
        discovered_host = self.context.get("discovered_host")

        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            profile = user_input.get(CONF_INTEGRATION_PROFILE, PROFILE_BASIC)

            if not host:
                errors[CONF_HOST] = "host_required"
            if not username:
                errors[CONF_USERNAME] = "username_required"
            if not password:
                errors[CONF_PASSWORD] = "password_required"

            if not errors:
                errors, device_name, serial_number = await self._async_validate_connection(
                    host, username, password, verify_ssl
                )

                if not errors:
                    self.context["user_input"] = {
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_INTEGRATION_PROFILE: profile,
                        "device_name": device_name,
                    }
                    self._detected_features = await self._async_probe_detected_features(
                        host, username, password, verify_ssl
                    )

                    if profile == PROFILE_BASIC:
                        entry_data = {
                            CONF_HOST: host,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_VERIFY_SSL: verify_ssl,
                            CONF_INTEGRATION_PROFILE: PROFILE_BASIC,
                            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                            CONF_SET_ALARM_SERVER: True,
                            CONF_ALARM_SERVER_HOST: await self._async_default_alarm_server(),
                        }
                        return await self._async_create_entry_from_context(
                            entry_data, device_name, host, verify_ssl
                        )

                    return await self.async_step_advanced()

        data_schema = await self._async_get_user_schema(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"discovered_host": discovered_host or ""},
        )

    async def async_step_advanced(self, user_input=None):
        """Handle advanced options step (initial setup only)."""
        errors: dict[str, str] = {}
        basic_data = self.context.get("user_input", {})
        if not basic_data:
            return self.async_abort(reason="no_basic_data")

        default_alarm_server = await self._async_default_alarm_server()

        if user_input is not None:
            set_alarm_server = user_input.get(CONF_SET_ALARM_SERVER, True)

            if CONF_SET_ALARM_SERVER in user_input and not any(
                k in user_input
                for k in (CONF_UPDATE_INTERVAL, CONF_ALARM_SERVER_HOST, RTSP_PORT_FORCED)
            ):
                schema = get_advanced_schema(
                    default_alarm_server, set_alarm_server=set_alarm_server
                )
                return self.async_show_form(
                    step_id="advanced", data_schema=schema, errors=errors
                )

            if set_alarm_server and not user_input.get(CONF_ALARM_SERVER_HOST, "").strip():
                errors[CONF_ALARM_SERVER_HOST] = "alarm_server_required"

            _validate_rtsp_port_field(user_input.get(RTSP_PORT_FORCED), errors)

            if not errors:
                self.context["advanced_options"] = {
                    CONF_UPDATE_INTERVAL: user_input.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                    CONF_SET_ALARM_SERVER: set_alarm_server,
                    CONF_ALARM_SERVER_HOST: (
                        user_input.get(CONF_ALARM_SERVER_HOST, default_alarm_server)
                        if set_alarm_server
                        else default_alarm_server
                    ),
                }
                rtsp_port = _parse_rtsp_port(user_input.get(RTSP_PORT_FORCED))
                if rtsp_port is not None:
                    self.context["advanced_options"][RTSP_PORT_FORCED] = rtsp_port
                self.context["saved_extra_groups"] = []
                self.context["default_entity_items"] = {}
                return await self.async_step_entity_customize()

            schema = get_advanced_schema(
                default_alarm_server, set_alarm_server=set_alarm_server
            )
            return self.async_show_form(
                step_id="advanced", data_schema=schema, errors=errors
            )

        schema = get_advanced_schema(default_alarm_server, set_alarm_server=True)
        return self.async_show_form(step_id="advanced", data_schema=schema, errors=errors)

    async def async_step_entity_customize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One screen: each extra category with its own entity checklist."""
        errors: dict[str, str] = {}
        detected = self._detected_features or self.context.get("detected_features") or {}

        if user_input is not None:
            groups, entity_items = parse_customize_submission(user_input)
            return await self._async_finish_advanced_setup(
                groups, entity_items, self._flow_supported_snapshot()
            )

        schema = self._entity_customize_schema(detected)
        if not schema.schema:
            if self.context.get("reconfigure_input"):
                return await self._async_finish_reconfigure_preserve_entities()
            return await self._async_finish_advanced_setup([], {})

        return self.async_show_form(
            step_id="entity_customize",
            data_schema=schema,
            errors=errors,
        )
