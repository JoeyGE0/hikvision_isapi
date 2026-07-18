"""Media player platform for Hikvision ISAPI."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_GROUP_TWO_WAY_AUDIO
from .device_helpers import get_primary_device_info
from .entity_profiles import entity_enabled

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(slots=True)
class _QueueItem:
    """Resolved item in the camera speaker queue."""

    media_type: MediaType | str
    media_id: str
    media_url: str
    title: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media player entity for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)
    detected_features = data.get("detected_features", {})

    entities = []
    if (
        entity_enabled(entry, ENTITY_GROUP_TWO_WAY_AUDIO, "media_player")
        and detected_features.get("media_player", False)
    ):
        entities.append(
            HikvisionMediaPlayer(
                coordinator, api, entry, host, device_name
            )
        )
    async_add_entities(entities)


class HikvisionMediaPlayer(MediaPlayerEntity):
    """Play Home Assistant media through the camera loudspeaker."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _attr_media_content_type = MediaType.MUSIC
    _attr_icon = "mdi:speaker"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator,
        api,
        entry: ConfigEntry,
        host: str,
        device_name: str,
    ) -> None:
        """Initialize the camera speaker."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Speaker"
        self._attr_unique_id = f"{host}_media_player"
        self._attr_state = MediaPlayerState.IDLE

        self._queue: list[_QueueItem] = []
        self._queue_index = 0
        self._stream_task: asyncio.Task | None = None
        self._stop_event: threading.Event | None = None
        self._media_position = 0.0
        self._position_updated_at: datetime | None = None
        self._last_state_write = 0.0
        self._is_muted = False
        self._volume_before_mute = 0.5

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(
            self.coordinator.hass, self._entry
        )

    @property
    def available(self) -> bool:
        """Return whether the camera is available."""
        return self.coordinator.last_update_success

    @property
    def volume_level(self) -> float | None:
        """Return camera loudspeaker volume from 0 to 1."""
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("speakerVolume")
            if volume is not None:
                return float(volume) / 100.0
        return None

    @property
    def is_volume_muted(self) -> bool:
        """Return whether the camera loudspeaker is muted."""
        return self._is_muted

    @property
    def media_content_id(self) -> str | None:
        """Return the current Home Assistant media ID."""
        item = self._current_item
        return item.media_id if item else None

    @property
    def media_title(self) -> str | None:
        """Return the current media title."""
        item = self._current_item
        return item.title if item else None

    @property
    def media_position(self) -> float | None:
        """Return current playback position."""
        return self._media_position if self._current_item else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return when playback position was last updated."""
        return self._position_updated_at

    @property
    def _current_item(self) -> _QueueItem | None:
        if 0 <= self._queue_index < len(self._queue):
            return self._queue[self._queue_index]
        return None

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve and play or enqueue Home Assistant media."""
        del announce
        item = await self._resolve_item(media_type, media_id)
        enqueue = enqueue or MediaPlayerEnqueue.REPLACE

        if enqueue == MediaPlayerEnqueue.ADD and self._queue:
            self._queue.append(item)
            self.async_write_ha_state()
            return

        if enqueue == MediaPlayerEnqueue.NEXT and self._queue:
            self._queue.insert(self._queue_index + 1, item)
            self.async_write_ha_state()
            return

        if enqueue == MediaPlayerEnqueue.PLAY and self._queue:
            self._queue.insert(self._queue_index + 1, item)
            await self._start_index(self._queue_index + 1)
            return

        self._queue = [item]
        self._queue_index = 0
        await self._start_current(0.0)

    async def _resolve_item(
        self, media_type: MediaType | str, media_id: str
    ) -> _QueueItem:
        """Resolve a media-source ID to an ffmpeg-readable URL."""
        media_url = media_id
        title = media_id.rsplit("/", 1)[-1] or "Camera audio"

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_url = async_process_play_media_url(
                self.hass, play_item.url
            )
            media_type = MediaType.MUSIC
            title = (
                getattr(play_item, "title", None)
                or media_id.rsplit("/", 1)[-1]
                or "Camera audio"
            )

        if not media_url.startswith(("http://", "https://")):
            raise ValueError(
                "Hikvision speaker media must resolve to an HTTP(S) URL"
            )
        return _QueueItem(media_type, media_id, media_url, title)

    async def _start_index(self, index: int) -> None:
        """Stop the current item and play another queue index."""
        await self._stop_stream()
        if not 0 <= index < len(self._queue):
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()
            return
        self._queue_index = index
        await self._start_current(0.0)

    async def _start_current(self, start_seconds: float) -> None:
        """Start streaming the current queue item."""
        item = self._current_item
        if item is None:
            return
        await self._stop_stream()

        stop_event = threading.Event()
        self._stop_event = stop_event
        self._media_position = max(0.0, start_seconds)
        self._position_updated_at = datetime.now(timezone.utc)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

        self._stream_task = self.hass.async_create_task(
            self._stream_audio(item, start_seconds, stop_event)
        )

    async def _stream_audio(
        self,
        item: _QueueItem,
        start_seconds: float,
        stop_event: threading.Event,
    ) -> None:
        """Stream one resolved URL in an executor."""
        loop = asyncio.get_running_loop()

        def progress(position: float) -> None:
            loop.call_soon_threadsafe(
                self._handle_progress, position, stop_event
            )

        success = False
        try:
            success = await self.hass.async_add_executor_job(
                self.api.play_audio_url,
                item.media_url,
                stop_event,
                start_seconds,
                progress,
            )
        except asyncio.CancelledError:
            stop_event.set()
            raise
        except Exception:
            _LOGGER.exception("Error streaming media to Hikvision speaker")
        finally:
            if self._stop_event is stop_event:
                self._stream_task = None
                self._stop_event = None
                if success:
                    self.hass.async_create_task(self._advance_after_end())
                elif self._attr_state == MediaPlayerState.PLAYING:
                    self._attr_state = MediaPlayerState.IDLE
                    self.async_write_ha_state()

    def _handle_progress(
        self, position: float, stop_event: threading.Event
    ) -> None:
        """Update HA playback position from the streaming thread."""
        if self._stop_event is not stop_event:
            return
        self._media_position = position
        self._position_updated_at = datetime.now(timezone.utc)
        now = time.monotonic()
        if now - self._last_state_write >= 1.0:
            self._last_state_write = now
            self.async_write_ha_state()

    async def _advance_after_end(self) -> None:
        """Advance naturally to the next queued item."""
        next_index = self._queue_index + 1
        if next_index < len(self._queue):
            self._queue_index = next_index
            await self._start_current(0.0)
            return
        self._attr_state = MediaPlayerState.IDLE
        self._media_position = 0.0
        self._position_updated_at = None
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Pause by closing talk and retaining the current position."""
        if self._attr_state != MediaPlayerState.PLAYING:
            return
        position = self._media_position
        self._attr_state = MediaPlayerState.PAUSED
        await self._stop_stream()
        self._media_position = position
        self._position_updated_at = None
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Resume paused media."""
        if (
            self._attr_state == MediaPlayerState.PAUSED
            and self._current_item is not None
        ):
            await self._start_current(self._media_position)

    async def async_media_stop(self) -> None:
        """Stop playback and close TwoWayAudio promptly."""
        await self._stop_stream()
        self._attr_state = MediaPlayerState.IDLE
        self._media_position = 0.0
        self._position_updated_at = None
        self.async_write_ha_state()

    async def _stop_stream(self) -> None:
        """Signal the worker and wait briefly for clean camera teardown."""
        stop_event = self._stop_event
        task = self._stream_task
        self._stop_event = None
        self._stream_task = None
        if stop_event is not None:
            stop_event.set()
        if task is not None and task is not asyncio.current_task():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                task.cancel()
        await self.hass.async_add_executor_job(
            self.api.close_audio_session
        )

    async def async_media_next_track(self) -> None:
        """Skip to the next queued item."""
        await self._start_index(self._queue_index + 1)

    async def async_media_previous_track(self) -> None:
        """Return to the previous queued item."""
        await self._start_index(max(0, self._queue_index - 1))

    async def async_media_seek(self, position: float) -> None:
        """Seek by reopening the stream at the requested position."""
        if self._current_item is None:
            return
        await self._start_current(max(0.0, position))

    async def async_clear_playlist(self) -> None:
        """Stop playback and clear the in-memory HA queue."""
        await self.async_media_stop()
        self._queue.clear()
        self._queue_index = 0
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set camera loudspeaker volume from 0 to 1."""
        volume_int = max(0, min(100, round(volume * 100)))
        success = await self.hass.async_add_executor_job(
            self.api.set_speaker_volume, volume_int
        )
        if success:
            self._is_muted = volume_int == 0
            if volume_int > 0:
                self._volume_before_mute = volume_int / 100
            await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or restore the camera loudspeaker."""
        if mute:
            current = self.volume_level
            if current is not None and current > 0:
                self._volume_before_mute = current
            await self.async_set_volume_level(0.0)
            return
        await self.async_set_volume_level(
            max(0.01, self._volume_before_mute)
        )

    async def async_volume_up(self) -> None:
        """Increase volume by ten percent."""
        await self.async_set_volume_level(
            min(1.0, (self.volume_level or 0.5) + 0.1)
        )

    async def async_volume_down(self) -> None:
        """Decrease volume by ten percent."""
        await self.async_set_volume_level(
            max(0.0, (self.volume_level or 0.5) - 0.1)
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant audio media sources."""
        del media_content_type
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: (
                item.media_content_type or ""
            ).startswith("audio/"),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop playback when the entity is removed."""
        await self.async_media_stop()
        await super().async_will_remove_from_hass()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator availability updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self.async_write_ha_state
            )
        )
