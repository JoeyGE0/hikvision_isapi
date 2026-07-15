"""Media player platform for Hikvision ISAPI."""
import asyncio
import logging
import threading
from typing import Any

import requests

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
    BrowseMedia,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, ENTITY_GROUP_TWO_WAY_AUDIO
from .entity_profiles import entity_enabled
from .device_helpers import get_primary_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
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
        entities.append(HikvisionMediaPlayer(coordinator, api, entry, host, device_name))

    async_add_entities(entities)


class HikvisionMediaPlayer(MediaPlayerEntity):
    """Media player for the camera loudspeaker.

    Browse any Home Assistant media source audio, then ffmpeg-convert to the
    camera's TwoWayAudio codec (AAC or G.711) and stream over ISAPI — same
    wire format as the backyard AAC lab / go2rtc ISAPI talk client.
    """

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _attr_media_content_type = MediaType.MUSIC
    _attr_unique_id = "hikvision_media_player"
    _attr_icon = "mdi:speaker"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the media player."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Speaker"
        self._attr_unique_id = f"{host}_media_player"
        self._playing = False
        self._stream_task: asyncio.Task | None = None
        self._stop_event: threading.Event | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.coordinator.data and "audio" in self.coordinator.data:
            volume = self.coordinator.data["audio"].get("speakerVolume")
            if volume is not None:
                return float(volume) / 100.0
        return None

    @property
    def state(self):
        """Return the state of the player."""
        if self._playing:
            return "playing"
        return "idle"

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play media through the camera speaker."""
        _LOGGER.info("Play media requested: %s (type: %s)", media_id, media_type)

        await self.async_media_stop()

        self._stop_event = threading.Event()
        self._playing = True
        self.async_write_ha_state()

        self._stream_task = self.hass.async_create_task(
            self._stream_audio(media_id, media_type, self._stop_event)
        )

    async def _stream_audio(
        self,
        media_id: str,
        media_type: str,
        stop_event: threading.Event,
    ) -> None:
        """Download media, convert via ffmpeg, stream over ISAPI."""
        try:
            audio_data = await self._get_audio_data(media_id, media_type)
            if not audio_data:
                _LOGGER.error("Failed to get audio data for: %s", media_id)
                return
            if stop_event.is_set():
                return

            _LOGGER.info(
                "Got %d bytes of media — converting to camera talk codec and streaming",
                len(audio_data),
            )
            success = await self.hass.async_add_executor_job(
                self.api.play_audio_bytes, audio_data, stop_event
            )
            if not success and not stop_event.is_set():
                _LOGGER.error("Failed to stream audio to camera")
        except asyncio.CancelledError:
            stop_event.set()
            raise
        except Exception as e:
            _LOGGER.error("Error streaming audio: %s", e, exc_info=True)
        finally:
            self._playing = False
            self._stream_task = None
            self.async_write_ha_state()

    async def _get_audio_data(self, media_id: str, media_type: str) -> bytes | None:
        """Get audio data from media_id (URL, TTS, or media-source)."""
        from homeassistant.components.media_source import (
            async_resolve_media,
            is_media_source_id,
        )

        try:
            # Handle media-source IDs first (includes TTS and local media)
            if is_media_source_id(media_id):
                try:
                    # Pattern from Home Assistant Cast and Sonos integrations:
                    # 1. Resolve media with entity_id (for proper URL generation)
                    # 2. Process URL with async_process_play_media_url
                    resolved_media = await async_resolve_media(
                        self.hass, media_id, self.entity_id
                    )
                    if resolved_media and resolved_media.url:
                        media_url = async_process_play_media_url(
                            self.hass, resolved_media.url
                        )
                        _LOGGER.info(
                            "Resolved media source: %s -> %s (processed: %s, mime: %s)",
                            media_id,
                            resolved_media.url,
                            media_url,
                            getattr(resolved_media, "mime_type", "unknown"),
                        )

                        if not media_url.startswith("http://") and not media_url.startswith(
                            "https://"
                        ):
                            _LOGGER.error(
                                "Invalid URL format after processing: %s", media_url
                            )
                            return None

                        session = async_get_clientsession(self.hass)
                        try:
                            _LOGGER.info("Downloading media via HTTP: %s", media_url)
                            async with session.get(
                                media_url, timeout=30, allow_redirects=True
                            ) as response:
                                response.raise_for_status()
                                data = await response.read()
                                _LOGGER.info(
                                    "Successfully downloaded %d bytes from %s",
                                    len(data),
                                    media_url,
                                )
                                return data
                        except Exception as e:
                            _LOGGER.error(
                                "Failed to download media from %s: %s",
                                media_url,
                                e,
                                exc_info=True,
                            )
                            return None
                    else:
                        _LOGGER.error("Failed to resolve media source URL")
                        return None
                except Exception as e:
                    _LOGGER.error("Failed to resolve media source: %s", e)
                    return None

            # Handle direct URLs
            if media_id.startswith("http://") or media_id.startswith("https://"):
                response = await self.hass.async_add_executor_job(
                    requests.get, media_id, {"timeout": 30}
                )
                response.raise_for_status()
                return response.content

            # Handle TTS (legacy format)
            if media_id.startswith("tts:"):
                try:
                    resolved_media = await async_resolve_media(self.hass, media_id)
                    if resolved_media and resolved_media.url:
                        media_url = resolved_media.url
                        if media_url.startswith("/"):
                            base_url = (
                                self.hass.config.internal_url
                                or self.hass.config.external_url
                            )
                            if not base_url:
                                base_url = "http://localhost:8123"
                            base_url = base_url.rstrip("/")
                            media_url = f"{base_url}{resolved_media.url}"
                            _LOGGER.info("Converted TTS URL to: %s", media_url)

                        if not media_url.startswith("http://") and not media_url.startswith(
                            "https://"
                        ):
                            _LOGGER.error("Invalid TTS URL format: %s", media_url)
                            return None

                        is_local = (
                            "localhost" in media_url
                            or "127.0.0.1" in media_url
                            or (
                                self.hass.config.internal_url
                                and self.hass.config.internal_url in media_url
                            )
                            or (
                                self.hass.config.external_url
                                and self.hass.config.external_url in media_url
                            )
                        )

                        if is_local:
                            session = async_get_clientsession(self.hass)
                            async with session.get(media_url, timeout=30) as response:
                                response.raise_for_status()
                                return await response.read()

                        response = await self.hass.async_add_executor_job(
                            requests.get, media_url, {"timeout": 30}
                        )
                        response.raise_for_status()
                        return response.content
                except Exception as e:
                    _LOGGER.error("Failed to get TTS audio: %s", e)
                _LOGGER.warning("TTS format not supported: %s", media_id)
                return None

            # Try as direct URL (fallback)
            try:
                response = await self.hass.async_add_executor_job(
                    requests.get, media_id, {"timeout": 30}
                )
                response.raise_for_status()
                return response.content
            except Exception:
                _LOGGER.error("Unsupported media_id format: %s", media_id)
                return None

        except Exception as e:
            _LOGGER.error("Failed to get audio data: %s", e)
            return None

    async def async_media_stop(self) -> None:
        """Stop media playback and close any open TwoWayAudio session."""
        if self._stop_event is not None:
            self._stop_event.set()

        task = self._stream_task
        self._stream_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await self.hass.async_add_executor_job(self.api.close_audio_session)

        was_playing = self._playing
        self._playing = False
        self._stop_event = None
        if was_playing:
            self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        volume_int = int(volume * 100)
        success = await self.hass.async_add_executor_job(
            self.api.set_speaker_volume, volume_int
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Turn volume up."""
        current = self.volume_level or 0.5
        await self.async_set_volume_level(min(1.0, current + 0.1))

    async def async_volume_down(self) -> None:
        """Turn volume down."""
        current = self.volume_level or 0.5
        await self.async_set_volume_level(max(0.0, current - 0.1))

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse media - shows audio files from media source."""
        from homeassistant.components.media_source import async_browse_media

        return await async_browse_media(
            self.hass,
            media_content_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop playback when entity is removed."""
        await self.async_media_stop()
        await super().async_will_remove_from_hass()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
