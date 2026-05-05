"""Data update coordinator for Hikvision ISAPI."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HikvisionISAPI, AuthenticationError
from .const import (
    DOMAIN,
    FEATURE_CAPABILITY_FIRST_SCAN,
    FEATURE_CAPABILITY_RESCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class HikvisionDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hikvision ISAPI data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HikvisionISAPI,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data['host']}",
            update_interval=timedelta(seconds=update_interval),
        )
        self._next_capability_scan = datetime.now(UTC) + FEATURE_CAPABILITY_FIRST_SCAN
        # Avoid entity flapping from transient probe failures: if a rescan would
        # remove capabilities, require the same reduced profile twice in a row.
        self._pending_capability_signature: str | None = None
        self._pending_capability_features: dict | None = None

    @staticmethod
    def _capability_signature(features: dict) -> str:
        """Stable string for comparing capability dicts."""
        if not features:
            return ""
        return json.dumps(sorted(features.items()), separators=(",", ":"))

    async def _async_maybe_rescan_capabilities(self) -> None:
        """Re-run feature detection; reload config entry if the capability set changes."""
        now = datetime.now(UTC)
        if now < self._next_capability_scan:
            return
        self._next_capability_scan = now + FEATURE_CAPABILITY_RESCAN_INTERVAL

        domain_data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if not domain_data:
            return
        old_features = domain_data.get("detected_features") or {}
        try:
            new_features = await self.hass.async_add_executor_job(self.api.detect_features)
        except Exception as err:
            _LOGGER.warning(
                "Capability re-scan failed for %s: %s",
                self.entry.data.get("host"),
                err,
            )
            return

        if not new_features and old_features:
            _LOGGER.warning(
                "Capability re-scan returned empty for %s; keeping previous profile",
                self.entry.data.get("host"),
            )
            return

        if self._capability_signature(old_features) == self._capability_signature(new_features):
            self._pending_capability_signature = None
            self._pending_capability_features = None
            return

        old_keys = {k for k, v in old_features.items() if v}
        new_keys = {k for k, v in new_features.items() if v}
        removed_keys = old_keys - new_keys

        if removed_keys:
            new_sig = self._capability_signature(new_features)
            if self._pending_capability_signature != new_sig:
                self._pending_capability_signature = new_sig
                self._pending_capability_features = new_features
                _LOGGER.info(
                    "Hikvision %s: capability reduction detected (%s); waiting for confirmation on next scan",
                    self.entry.data.get("host"),
                    ", ".join(sorted(removed_keys)),
                )
                return

            _LOGGER.info(
                "Hikvision %s: capability reduction confirmed (%s); applying profile update",
                self.entry.data.get("host"),
                ", ".join(sorted(removed_keys)),
            )

        self._pending_capability_signature = None
        self._pending_capability_features = None

        _LOGGER.info(
            "Hikvision %s: capability profile changed; reloading config entry to update entities",
            self.entry.data.get("host"),
        )
        self.api.detected_features = new_features
        domain_data["detected_features"] = new_features

        entry_id = self.entry.entry_id
        hass = self.hass

        def _reload_entry(_now: datetime) -> None:
            hass.async_create_task(hass.config_entries.async_reload(entry_id))

        async_call_later(hass, 2, _reload_entry)

    async def _async_update_data(self) -> dict:
        """Fetch data from Hikvision ISAPI."""
        try:
            domain_data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
            detected_features = domain_data.get("detected_features") or {}
            capabilities = domain_data.get("capabilities") or {}

            # Fetch camera state only for supported capabilities to avoid hammering
            # unsupported/forbidden endpoints (prevents 403 log spam).
            has_ir = any(
                detected_features.get(key, False)
                for key in ("ir_sensitivity", "ir_filter_time", "day_night_mode")
            )
            ircut_data = (
                await self.hass.async_add_executor_job(self.api.get_ircut_filter)
                if has_ir
                else {}
            )

            has_supplement_light = any(
                detected_features.get(key, False)
                for key in (
                    "supplement_light_mode",
                    "white_light_time",
                    "white_light_brightness",
                    "ir_light_brightness",
                    "white_light_brightness_limit",
                    "ir_light_brightness_limit",
                )
            )
            supplement_light = (
                await self.hass.async_add_executor_job(self.api.get_supplement_light)
                if has_supplement_light
                else {}
            )

            has_two_way_audio = any(
                detected_features.get(key, False)
                for key in (
                    "speaker_volume",
                    "microphone_volume",
                    "noise_reduce",
                    "media_player",
                )
            )
            audio_data = (
                await self.hass.async_add_executor_job(self.api.get_two_way_audio)
                if has_two_way_audio
                else {}
            )

            motion_data = (
                await self.hass.async_add_executor_job(self.api.get_motion_detection)
                if detected_features.get("motion_detection", False)
                else {}
            )
            tamper_data = (
                await self.hass.async_add_executor_job(self.api.get_tamper_detection)
                if detected_features.get("tamper_detection", False)
                else {}
            )
            field_detection = (
                await self.hass.async_add_executor_job(self.api.get_field_detection)
                if detected_features.get("intrusion_detection", False)
                else {}
            )
            line_detection = (
                await self.hass.async_add_executor_job(self.api.get_line_detection)
                if detected_features.get("line_crossing_detection", False)
                else {}
            )
            scene_change = (
                await self.hass.async_add_executor_job(self.api.get_scene_change_detection)
                if detected_features.get("scene_change_detection", False)
                else {}
            )
            region_entrance = (
                await self.hass.async_add_executor_job(self.api.get_region_entrance)
                if detected_features.get("region_entrance_detection", False)
                else {}
            )
            region_exiting = (
                await self.hass.async_add_executor_job(self.api.get_region_exiting)
                if detected_features.get("region_exiting_detection", False)
                else {}
            )
            white_light_time = (
                await self.hass.async_add_executor_job(self.api.get_white_light_time)
                if detected_features.get("white_light_time", False)
                else {}
            )

            has_color = any(
                detected_features.get(key, False)
                for key in ("brightness", "contrast", "saturation")
            )
            color_data = (
                await self.hass.async_add_executor_job(self.api.get_color)
                if has_color
                else {}
            )
            sharpness_data = (
                await self.hass.async_add_executor_job(self.api.get_sharpness)
                if detected_features.get("sharpness", False)
                else {}
            )
            audio_alarm_data = None
            audio_alarm_caps_raw = None
            if any(
                detected_features.get(key, False)
                for key in (
                    "alarm_times",
                    "loudspeaker_volume",
                    "audio_alarm_type",
                    "audio_alarm_sound",
                    "test_audio_alarm",
                )
            ):
                audio_alarm_data = await self.hass.async_add_executor_job(
                    self.api.get_audio_alarm
                )
                audio_alarm_caps_raw = await self.hass.async_add_executor_job(
                    self.api.get_audio_alarm_capabilities
                )
            system_status = await self.hass.async_add_executor_job(
                self.api.get_system_status
            )
            streaming_status = await self.hass.async_add_executor_job(
                self.api.get_streaming_status
            )
            alarm_input = {}
            if (
                capabilities.get("input_ports", 0) > 0
                and detected_features.get("alarm_input", False)
            ):
                alarm_input = await self.hass.async_add_executor_job(
                    self.api.get_alarm_input, 1
                )
            alarm_server = await self.hass.async_add_executor_job(
                self.api.get_alarm_server
            )
            from homeassistant.components.switch import ENTITY_ID_FORMAT
            from homeassistant.util import slugify
            
            data = {
                "ircut": ircut_data,
                "supplement_light": supplement_light,
                "audio": audio_data,
                "motion": motion_data,
                "tamper": tamper_data,
                "field_detection": field_detection,
                "line_detection": line_detection,
                "scene_change": scene_change,
                "region_entrance": region_entrance,
                "region_exiting": region_exiting,
                "white_light_time": white_light_time,
                "color": color_data,
                "sharpness": sharpness_data,
                "audio_alarm": audio_alarm_data.get("AudioAlarm") if audio_alarm_data else None,
                "audio_alarm_capabilities": HikvisionISAPI.normalize_audio_alarm_capabilities(
                    audio_alarm_caps_raw
                ),
                "system_status": system_status,
                "streaming_status": streaming_status,
                "alarm_input": alarm_input,
                "alarm_server": alarm_server,
            }
            
            # Store alarm output status using unique_id as key only when the model has outputs.
            if (
                capabilities.get("output_ports", 0) > 0
                and detected_features.get("alarm_output", False)
            ):
                alarm_output = await self.hass.async_add_executor_job(
                    self.api.get_alarm_output, 1
                )
                # Get device name from stored data (with fallback if not available yet)
                from .const import DOMAIN
                device_info = {}
                if DOMAIN in self.hass.data and self.entry.entry_id in self.hass.data[DOMAIN]:
                    device_info = self.hass.data[DOMAIN][self.entry.entry_id].get("device_info", {})
                device_name = device_info.get("deviceName", self.entry.data.get("host", ""))
                _id = ENTITY_ID_FORMAT.format(f"{slugify(device_name.lower())}_1_alarm_output")
                data[_id] = alarm_output.get("enabled", False)

            await self._async_maybe_rescan_capabilities()

            return data
        except AuthenticationError as err:
            raise UpdateFailed(
                f"Authentication failed. Please check your username and password in the integration settings. "
                f"Note: Username is case-sensitive (e.g., 'admin' not 'Admin'). Error: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

