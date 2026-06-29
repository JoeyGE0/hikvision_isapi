"""Siren platform for Hikvision ISAPI."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIREN_RETRIGGER_INTERVAL_SECONDS, SIREN_TONE_SWITCH_SETTLE_SECONDS
from .device_helpers import get_primary_device_info
from .api import HikvisionISAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up siren entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)
    detected_features = data.get("detected_features", {})

    if not detected_features.get("test_audio_alarm", False):
        async_add_entities([])
        return

    async_add_entities([HikvisionAudioAlarmSiren(coordinator, api, entry, host, device_name)])


class HikvisionAudioAlarmSiren(SirenEntity):
    """Siren entity backed by Hikvision AudioAlarm trigger endpoint."""

    _attr_icon = "mdi:alarm-bell"
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TONES
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str) -> None:
        """Initialize the siren."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Alarm"
        self._attr_unique_id = f"{host}_audio_alarm_siren"
        self._attr_is_on = False
        self._loop_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._active_tone_id: int | None = None
        self._active_volume_level: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._attr_is_on

    @property
    def available_tones(self) -> dict[str, int] | list[str] | None:
        """Return supported tones (human-readable labels, same as Warning Sound select).

        Home Assistant often displays **values** for dict-based tones (showing 1–14). Use a
        sorted list of labels so the UI matches ``select.*_warning_sound``.
        """
        labels = self._tone_labels_ordered()
        return labels if labels else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        duration = kwargs.get(ATTR_DURATION)
        tone = kwargs.get(ATTR_TONE)
        volume_level = kwargs.get(ATTR_VOLUME_LEVEL)

        previous_tone_id = self._active_tone_id
        was_on = self._attr_is_on
        explicit_tone = tone is not None
        explicit_volume = volume_level is not None

        tone_id = self._resolve_tone_id(tone) if explicit_tone else None
        if explicit_tone and tone_id is None:
            _LOGGER.error(
                "Unknown siren tone %r on %s — available: %s",
                tone,
                self._host,
                self._tone_labels_ordered(),
            )
            return

        volume_percent = self._resolve_volume_percent(volume_level)

        cap_rows = self._capability_warning_rows_only()
        if not explicit_tone and not explicit_volume:
            tone_id, volume_percent = self._audio_config_from_coordinator()
            if tone_id is None:
                _LOGGER.error(
                    "No audio alarm tone in coordinator for %s — siren not started",
                    self._host,
                )
                return

            audio_class = HikvisionISAPI.resolve_audio_class_for_sound_id(tone_id, cap_rows)
            _LOGGER.debug(
                "Restoring siren on %s from coordinator: tone_id=%s class=%s volume=%s",
                self._host,
                tone_id,
                audio_class,
                volume_percent,
            )
            success = await self.hass.async_add_executor_job(
                self.api.set_audio_alarm, audio_class, tone_id, volume_percent, None
            )
            if not success:
                _LOGGER.error(
                    "Failed to restore audio alarm config on %s — siren not started",
                    self._host,
                )
                return

            configured_id = await self.hass.async_add_executor_job(
                self.api.get_configured_audio_id
            )
            if configured_id != tone_id:
                _LOGGER.error(
                    "Audio alarm on %s reports audioID %s after restore (wanted %s) — siren not started",
                    self._host,
                    configured_id,
                    tone_id,
                )
                return

            self._active_tone_id = tone_id
            self._active_volume_level = (
                volume_percent / 100.0 if volume_percent is not None else None
            )
        else:
            if volume_percent is not None:
                self._active_volume_level = volume_percent / 100.0

            if tone_id is not None:
                audio_class = HikvisionISAPI.resolve_audio_class_for_sound_id(tone_id, cap_rows)
                _LOGGER.debug(
                    "Setting siren on %s: tone_id=%s class=%s volume=%s",
                    self._host,
                    tone_id,
                    audio_class,
                    volume_percent,
                )
                success = await self.hass.async_add_executor_job(
                    self.api.set_audio_alarm, audio_class, tone_id, volume_percent, None
                )
                if not success:
                    _LOGGER.error(
                        "Failed to set audio alarm tone %s on %s — siren not started",
                        tone_id,
                        self._host,
                    )
                    return

                configured_id = await self.hass.async_add_executor_job(
                    self.api.get_configured_audio_id
                )
                if configured_id != tone_id:
                    _LOGGER.error(
                        "Audio alarm on %s reports audioID %s after requesting %s — siren not started",
                        self._host,
                        configured_id,
                        tone_id,
                    )
                    return

                self._active_tone_id = tone_id
            elif volume_percent is not None:
                if self._active_tone_id is None:
                    self._active_tone_id = self._current_audio_id_from_coordinator()
                success = await self.hass.async_add_executor_job(
                    self.api.set_audio_alarm, None, None, volume_percent, None
                )
                if not success:
                    _LOGGER.error(
                        "Failed to set audio alarm volume on %s — siren not started",
                        self._host,
                    )
                    return
            elif self._active_tone_id is None:
                self._active_tone_id = self._current_audio_id_from_coordinator()

        if self._active_tone_id is None:
            _LOGGER.error(
                "No audio alarm tone configured on %s and none requested — siren not started",
                self._host,
            )
            return

        await self.async_turn_off()
        if (
            was_on
            and tone_id is not None
            and previous_tone_id is not None
            and tone_id != previous_tone_id
        ):
            await asyncio.sleep(SIREN_TONE_SWITCH_SETTLE_SECONDS)

        self._stop_event.clear()
        self._attr_is_on = True
        self.async_write_ha_state()

        self._loop_task = self.hass.async_create_task(self._async_trigger_loop(duration))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off.

        Camera firmware does not expose a direct stop endpoint; this stops retriggers.
        """
        self._stop_event.set()
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._loop_task = None
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    def _capability_warning_rows_only(self) -> list[dict]:
        """Capability warning sounds only (no synthetic current-ID row)."""
        norm = (self.coordinator.data or {}).get("audio_alarm_capabilities") or {}
        return [
            dict(r) for r in (norm.get("warning_sounds") or []) if isinstance(r, dict)
        ]

    def _current_audio_id_from_coordinator(self) -> int | None:
        """Active audio ID from coordinator snapshot."""
        audio_alarm = (self.coordinator.data or {}).get("audio_alarm") or {}
        raw = audio_alarm.get("audioID")
        if raw is None:
            raw = audio_alarm.get("alertAudioID")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _volume_percent_from_coordinator(self) -> int | None:
        """Alarm output volume (0–100) from coordinator snapshot."""
        audio_alarm = (self.coordinator.data or {}).get("audio_alarm") or {}
        raw = audio_alarm.get("audioVolume")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _audio_config_from_coordinator(self) -> tuple[int | None, int | None]:
        """Warning sound + volume as shown by HA entities (coordinator snapshot)."""
        return (
            self._current_audio_id_from_coordinator(),
            self._volume_percent_from_coordinator(),
        )

    def _tone_options_from_capabilities(self) -> dict[int, str]:
        """Build id -> label map (mirrors Warning Sound select logic)."""
        norm = (self.coordinator.data or {}).get("audio_alarm_capabilities") or {}
        rows: list[dict] = [
            dict(r) for r in (norm.get("warning_sounds") or []) if isinstance(r, dict)
        ]
        seen_ids: set[int] = set()
        for r in rows:
            try:
                seen_ids.add(int(r["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        audio_alarm = (self.coordinator.data or {}).get("audio_alarm") or {}
        raw_cur = audio_alarm.get("audioID")
        if raw_cur is None:
            raw_cur = audio_alarm.get("alertAudioID")
        if raw_cur is not None:
            try:
                cur_id = int(raw_cur)
            except (TypeError, ValueError):
                cur_id = None
            if cur_id is not None and cur_id not in seen_ids:
                rows.append({"id": cur_id, "label": f"Sound #{cur_id} (current)"})
        rows.sort(key=lambda r: int(r["id"]))

        options: dict[int, str] = {}
        for row in rows:
            try:
                aid = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            label = str(row.get("label") or f"Sound {aid}")
            options[aid] = label
        return options

    def _tone_labels_ordered(self) -> list[str]:
        """Labels sorted by audio id (for siren.tone UI)."""
        options = self._tone_options_from_capabilities()
        return [options[aid] for aid in sorted(options.keys())]

    def _resolve_tone_id(self, tone: Any) -> int | None:
        """Resolve tone parameter to an audio ID."""
        if tone is None:
            return None

        options = self._tone_options_from_capabilities()
        labels = self._tone_labels_ordered()
        normalize = HikvisionISAPI.normalize_alert_sound_label_for_compare

        if isinstance(tone, int):
            if tone in options:
                return tone
            if 0 <= tone < len(labels):
                return self._resolve_tone_id(labels[tone])
            return None

        if isinstance(tone, str):
            tone_str = tone.strip()
            if not tone_str:
                return None
            if tone_str.isdigit():
                numeric = int(tone_str)
                if numeric in options:
                    return numeric
                if 0 <= numeric < len(labels):
                    return self._resolve_tone_id(labels[numeric])
                return None

            tone_norm = normalize(tone_str)
            for aid, label in options.items():
                if tone_str == label or tone_norm == normalize(label):
                    return aid
        return None

    def _resolve_volume_percent(self, volume_level: Any) -> int | None:
        """Resolve siren volume level (0..1) to camera percentage (0..100)."""
        if volume_level is None:
            return None

        try:
            v = float(volume_level)
        except (TypeError, ValueError):
            return None
        v = max(0.0, min(1.0, v))
        return int(round(v * 100))

    async def _async_trigger_loop(self, duration: int | None) -> None:
        """Keep triggering alarm until duration ends or turn_off is called."""
        deadline: datetime | None = None
        if duration is not None:
            try:
                duration_int = max(1, int(duration))
                deadline = datetime.now() + timedelta(seconds=duration_int)
            except (TypeError, ValueError):
                deadline = None

        play_id = self._active_tone_id
        try:
            while not self._stop_event.is_set():
                await self.hass.async_add_executor_job(
                    self.api.trigger_audio_alarm, play_id
                )

                if deadline is not None and datetime.now() >= deadline:
                    break
                await asyncio.sleep(SIREN_RETRIGGER_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            pass
        finally:
            self._attr_is_on = False
            self._loop_task = None
            self.async_write_ha_state()
