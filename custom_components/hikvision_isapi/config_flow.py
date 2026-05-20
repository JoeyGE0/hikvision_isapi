"""Config flow for the Hikvision ISAPI integration."""
from __future__ import annotations

import copy
import logging
from typing import Any
import xml.etree.ElementTree as ET

import requests
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.components.network import async_get_source_ip
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.device_registry import format_mac

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    CONF_SET_ALARM_SERVER,
    CONF_ALARM_SERVER_HOST,
    CONF_VERIFY_SSL,
    RTSP_PORT_FORCED,
)
from .api import _extract_error_message

_XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"

# Never pre-fill password in UI suggestions (HA security + avoids config flow crashes).
_SENSITIVE_SUGGEST_KEYS = frozenset({CONF_PASSWORD})


def _optional_rtsp_port_schema():
    """Optional RTSP port: empty / omitted means unset (fixes '' vs vol.Coerce(int))."""

    def _coerce(v):
        if v is None or v == "":
            return None
        if isinstance(v, str) and not str(v).strip():
            return None
        try:
            port = int(v)
        except (ValueError, TypeError) as err:
            raise vol.Invalid("invalid_rtsp_port") from err
        if not 1 <= port <= 65535:
            raise vol.Invalid("invalid_rtsp_port")
        return port

    return vol.All(vol.Any(None, "", int, str, float), _coerce)


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
        if key == RTSP_PORT_FORCED and value is None:
            continue
        filtered[key] = value
    return filtered


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
    # Fallback for older HA: copy markers with suggested_value in description.
    schema: dict = {}
    for key, value in data_schema.schema.items():
        if not isinstance(key, vol.Marker):
            continue
        if key.schema in suggested:
            new_key = copy.copy(key)
            description = dict(new_key.description or {})
            description["suggested_value"] = suggested[key.schema]
            new_key.description = description
            schema[new_key] = value
        else:
            schema[key] = value
    return vol.Schema(schema)


def get_basic_schema(default_host: str | None = None):
    """Get basic schema for initial setup (legacy helper for tests)."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=default_host or ""): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("configure_advanced", default=False): bool,
    })


def get_advanced_schema(default_alarm_server: str | None = None, set_alarm_server: bool = True):
    """Get advanced options schema (initial setup advanced step)."""
    schema: dict = {
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
        vol.Required(CONF_SET_ALARM_SERVER, default=set_alarm_server): bool,
        vol.Optional(RTSP_PORT_FORCED): _optional_rtsp_port_schema(),
    }
    if set_alarm_server:
        schema[vol.Required(CONF_ALARM_SERVER_HOST, default=default_alarm_server or "")] = str
    return vol.Schema(schema)


def _reconfigure_schema() -> vol.Schema:
    """Static reconfigure/reauth schema (must not change shape between form loads)."""
    return vol.Schema({
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_VERIFY_SSL): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
        vol.Required(CONF_SET_ALARM_SERVER): bool,
        vol.Optional(CONF_ALARM_SERVER_HOST): str,
        vol.Optional(RTSP_PORT_FORCED): _optional_rtsp_port_schema(),
    })


class HikvisionISAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow handler."""
        self._discovered_host: str | None = None
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

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
        suggested.setdefault("configure_advanced", False)

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_VERIFY_SSL): bool,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional("configure_advanced"): bool,
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
            url = f"http://{host}/ISAPI/System/deviceInfo"
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(
                    url,
                    auth=(username, password),
                    verify=verify_ssl,
                    timeout=10,
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
        host = user_input[CONF_HOST].strip()
        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_USERNAME: user_input[CONF_USERNAME].strip(),
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, True),
            CONF_UPDATE_INTERVAL: user_input.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            ),
            CONF_SET_ALARM_SERVER: user_input.get(CONF_SET_ALARM_SERVER, True),
        }
        if data[CONF_SET_ALARM_SERVER]:
            data[CONF_ALARM_SERVER_HOST] = user_input.get(CONF_ALARM_SERVER_HOST, "").strip()
        elif self._reconfigure_entry:
            data[CONF_ALARM_SERVER_HOST] = self._reconfigure_entry.data.get(
                CONF_ALARM_SERVER_HOST, ""
            )
        if RTSP_PORT_FORCED in user_input:
            data[RTSP_PORT_FORCED] = user_input[RTSP_PORT_FORCED]
        elif self._reconfigure_entry and RTSP_PORT_FORCED in self._reconfigure_entry.data:
            data[RTSP_PORT_FORCED] = self._reconfigure_entry.data[RTSP_PORT_FORCED]
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
            password = user_input.get(CONF_PASSWORD, "")

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

            if not errors:
                verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
                errors, device_name, serial_number = await self._async_validate_connection(
                    host, username, password, verify_ssl
                )
                if not errors:
                    entry_data = self._build_entry_data(user_input)
                    if serial_number:
                        await self.async_set_unique_id(
                            serial_number, raise_on_progress=False
                        )
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=entry_data,
                        title=device_name,
                    )

        base_schema = _reconfigure_schema()
        data_schema = _apply_suggested_values(self, base_schema, dict(entry.data))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
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
                    entry_data = self._build_entry_data(user_input)
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=entry_data,
                    )

        # Reauth uses a smaller schema (credentials + host only)
        base_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_VERIFY_SSL): bool,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        data_schema = _apply_suggested_values(self, base_schema, dict(entry.data))
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
            configure_advanced = user_input.get("configure_advanced", False)

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
                        "device_name": device_name,
                    }

                    if configure_advanced:
                        return await self.async_step_advanced()

                    entry_data = {
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                        CONF_SET_ALARM_SERVER: True,
                        CONF_ALARM_SERVER_HOST: await self._async_default_alarm_server(),
                    }

                    unique_id = serial_number or self.unique_id or host
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=device_name, data=entry_data)

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

            if not errors:
                entry_data = {
                    **basic_data,
                    CONF_UPDATE_INTERVAL: user_input.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                    CONF_SET_ALARM_SERVER: set_alarm_server,
                    CONF_ALARM_SERVER_HOST: (
                        user_input.get(CONF_ALARM_SERVER_HOST, default_alarm_server)
                        if set_alarm_server
                        else default_alarm_server
                    ),
                    RTSP_PORT_FORCED: user_input.get(RTSP_PORT_FORCED),
                }
                device_name = entry_data.pop("device_name", basic_data.get(CONF_HOST, "Hikvision"))

                host = entry_data[CONF_HOST]
                verify_ssl = entry_data.get(CONF_VERIFY_SSL, True)
                _, _, serial_number = await self._async_validate_connection(
                    host,
                    entry_data[CONF_USERNAME],
                    entry_data[CONF_PASSWORD],
                    verify_ssl,
                )
                unique_id = serial_number or self.unique_id or host
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=device_name, data=entry_data)

            schema = get_advanced_schema(
                default_alarm_server, set_alarm_server=set_alarm_server
            )
            return self.async_show_form(
                step_id="advanced", data_schema=schema, errors=errors
            )

        schema = get_advanced_schema(default_alarm_server, set_alarm_server=True)
        return self.async_show_form(step_id="advanced", data_schema=schema, errors=errors)
