"""Media player platform for Hikvision ISAPI."""
import asyncio
import logging
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

from .const import DOMAIN
from .device_helpers import get_primary_device_info

_LOGGER = logging.getLogger(__name__)


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
    
    # Only add media player if two-way audio is supported
    if detected_features.get("media_player", False):
        entities.append(HikvisionMediaPlayer(coordinator, api, entry, host, device_name))

    async_add_entities(entities)


class HikvisionMediaPlayer(MediaPlayerEntity):
    """Media player entity for Hikvision camera speaker.

    Downloads media from Home Assistant (local media, TTS, URLs), converts to
    G.711 (8 kHz mono) when needed, then streams to the camera in paced chunks.
    """

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
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
        self._audio_session_id = None
        self._volume_level = None

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
        if self._audio_session_id:
            return "playing"
        return "idle"

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play media."""
        _LOGGER.info("Play media requested: %s (type: %s)", media_id, media_type)
        
        # Enable two-way audio first
        await self.hass.async_add_executor_job(
            self._enable_two_way_audio
        )
        
        # For Hikvision, audio streaming might not need explicit session opening
        # Some cameras stream directly when enabled. Let's try streaming.
        self._audio_session_id = "active"  # Mark as active
        self.async_write_ha_state()
        
        # Stream audio in background
        asyncio.create_task(self._stream_audio(media_id, media_type))
    
    def _enable_two_way_audio(self):
        """Enable two-way audio channel."""
        self.api.ensure_two_way_audio_enabled()
    
    async def _stream_audio(self, media_id: str, media_type: str):
        """Stream audio to camera."""
        try:
            # Get audio data
            audio_data = await self._get_audio_data(media_id, media_type)
            if not audio_data:
                _LOGGER.error("Failed to get audio data for: %s", media_id)
                await self.async_media_stop()
                return
            
            # Extract or convert to G.711 for the camera codec
            _LOGGER.debug("Preparing G.711 audio from %d bytes", len(audio_data))
            ulaw_data = await self.hass.async_add_executor_job(
                self._prepare_g711_audio, audio_data, media_id
            )
            
            if not ulaw_data:
                _LOGGER.error(
                    "Could not prepare G.711 audio. Install ffmpeg on Home Assistant "
                    "and use a supported source (MP3, WAV, TTS, or pre-encoded .ulaw)."
                )
                await self.async_media_stop()
                return
            
            _LOGGER.debug("Successfully extracted %d bytes of ulaw data, sending to camera", len(ulaw_data))
            
            # Stream to camera (128-byte chunks paced on persistent TCP socket)
            success = await self.hass.async_add_executor_job(
                self.api.stream_two_way_audio, ulaw_data
            )
            if not success:
                _LOGGER.error("Failed to stream audio to camera")
            
            # Close session after streaming
            await self.async_media_stop()
            
        except Exception as e:
            _LOGGER.error("Error streaming audio: %s", e, exc_info=True)
            await self.async_media_stop()
    
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
                    resolved_media = await async_resolve_media(self.hass, media_id, self.entity_id)
                    if resolved_media and resolved_media.url:
                        # Use Home Assistant's async_process_play_media_url to process the URL
                        # This is what Cast and Sonos integrations use (see cast/media_player.py and sonos/media_player.py)
                        # It handles authentication and URL conversion properly
                        # Default allow_relative_url=False converts relative URLs to absolute (needed for downloading)
                        media_url = async_process_play_media_url(self.hass, resolved_media.url)
                        _LOGGER.info("Resolved media source: %s -> %s (processed: %s, mime: %s)", 
                                   media_id, resolved_media.url, media_url, getattr(resolved_media, 'mime_type', 'unknown'))
                        
                        if not media_url.startswith("http://") and not media_url.startswith("https://"):
                            _LOGGER.error("Invalid URL format after processing: %s", media_url)
                            return None
                        
                        # Download via HTTP with Home Assistant authentication
                        # async_process_play_media_url handles authentication properly
                        session = async_get_clientsession(self.hass)
                        try:
                            _LOGGER.info("Downloading media via HTTP: %s", media_url)
                            async with session.get(media_url, timeout=30, allow_redirects=True) as response:
                                response.raise_for_status()
                                data = await response.read()
                                _LOGGER.info("Successfully downloaded %d bytes from %s", len(data), media_url)
                                return data
                        except Exception as e:
                            _LOGGER.error("Failed to download media from %s: %s", media_url, e, exc_info=True)
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
                # Try to resolve as media source
                try:
                    resolved_media = await async_resolve_media(self.hass, media_id)
                    if resolved_media and resolved_media.url:
                        # Convert relative URL to full URL if needed
                        media_url = resolved_media.url
                        if media_url.startswith("/"):
                            base_url = self.hass.config.internal_url or self.hass.config.external_url
                            if not base_url:
                                base_url = "http://localhost:8123"
                            base_url = base_url.rstrip("/")
                            media_url = f"{base_url}{resolved_media.url}"
                            _LOGGER.info("Converted TTS URL to: %s", media_url)
                        
                        # Validate URL
                        if not media_url.startswith("http://") and not media_url.startswith("https://"):
                            _LOGGER.error("Invalid TTS URL format: %s", media_url)
                            return None
                        
                        # Use Home Assistant's authenticated HTTP client for local URLs
                        is_local = (
                            "localhost" in media_url or 
                            "127.0.0.1" in media_url or
                            (self.hass.config.internal_url and self.hass.config.internal_url in media_url) or 
                            (self.hass.config.external_url and self.hass.config.external_url in media_url)
                        )
                        
                        if is_local:
                            session = async_get_clientsession(self.hass)
                            async with session.get(media_url, timeout=30) as response:
                                response.raise_for_status()
                                return await response.read()
                        else:
                            response = await self.hass.async_add_executor_job(
                                requests.get, media_url, {"timeout": 30}
                            )
                            response.raise_for_status()
                            return response.content
                except Exception as e:
                    _LOGGER.error("Failed to get TTS audio: %s", e)
                _LOGGER.warning("TTS format not supported: %s", media_id)
                return None
            
            # Try as direct file path or URL (fallback)
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
    
    def _prepare_g711_audio(self, audio_data: bytes, media_id: str = "") -> bytes | None:
        """Return raw G.711 bytes ready for ISAPI streaming."""
        if len(audio_data) < 12:
            _LOGGER.error("File too small to be valid audio")
            return None

        if media_id:
            media_lower = media_id.lower()
            if media_lower.endswith((".ulaw", ".pcm", ".alaw")):
                _LOGGER.info("Using raw G.711 file")
                return audio_data

        if audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
            g711 = self._extract_g711_from_wav(audio_data)
            if g711:
                return g711
            _LOGGER.info("WAV is not pre-encoded G.711; converting with ffmpeg")

        return self._convert_to_g711(audio_data)

    def _convert_to_g711(self, audio_data: bytes) -> bytes | None:
        """Convert arbitrary audio (MP3, PCM WAV, TTS, etc.) to raw G.711."""
        from io import BytesIO

        try:
            from pydub import AudioSegment
        except ImportError:
            _LOGGER.error("pydub is not available; cannot convert audio to G.711")
            return None

        compression = "G.711ulaw"
        try:
            audio_config = self.api.get_two_way_audio()
            if audio_config.get("audioCompressionType"):
                compression = audio_config["audioCompressionType"]
        except Exception:
            pass

        use_alaw = "alaw" in compression.lower()
        ffmpeg_codec = "pcm_alaw" if use_alaw else "pcm_mulaw"

        try:
            segment = AudioSegment.from_file(BytesIO(audio_data))
            segment = segment.set_frame_rate(8000).set_channels(1)
            out = BytesIO()
            segment.export(
                out,
                format="wav",
                codec=ffmpeg_codec,
                parameters=["-ar", "8000", "-ac", "1"],
            )
            wav_bytes = out.getvalue()
            _LOGGER.info(
                "Converted audio to G.711 %s (%d -> %d bytes)",
                "alaw" if use_alaw else "ulaw",
                len(audio_data),
                len(wav_bytes),
            )
            return self._extract_g711_from_wav(wav_bytes)
        except Exception as e:
            _LOGGER.error(
                "Audio conversion failed — is ffmpeg installed on Home Assistant? %s",
                e,
            )
            return None

    def _extract_g711_from_wav(self, wav_data: bytes) -> bytes | None:
        """Extract raw G.711 payload from a G.711 WAV (ulaw or alaw)."""
        import io
        import wave

        try:
            with wave.open(io.BytesIO(wav_data), "rb") as wf:
                if wf.getcomptype() in ("ULAW", "ulaw", "ULAW"):
                    frames = wf.readframes(wf.getnframes())
                    _LOGGER.info("Extracted %d bytes of G.711ulaw via wave module", len(frames))
                    return frames
                if wf.getcomptype() in ("ALAW", "alaw", "ALAW"):
                    frames = wf.readframes(wf.getnframes())
                    _LOGGER.info("Extracted %d bytes of G.711alaw via wave module", len(frames))
                    return frames
        except Exception:
            pass

        return self._extract_g711_from_wav_manual(wav_data)

    def _extract_g711_from_wav_manual(self, wav_data: bytes) -> bytes | None:
        try:
            # Check WAV header
            if wav_data[:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
                _LOGGER.error("Not a valid WAV file")
                return None
            
            # Find audio format code (offset 20-21)
            if len(wav_data) < 22:
                _LOGGER.error("WAV file too small")
                return None
            
            audio_format = int.from_bytes(wav_data[20:22], byteorder='little')
            
            # Check if it's G.711ulaw (0x0007) or G.711alaw (0x0006)
            if audio_format == 0x0007:  # G.711ulaw
                codec_name = "G.711ulaw"
            elif audio_format == 0x0006:  # G.711alaw
                codec_name = "G.711alaw"
            else:
                _LOGGER.debug(
                    "WAV codec 0x%04x is not G.711; conversion required", audio_format
                )
                return None
            
            # Check channels (offset 22-23) - should be 1 (mono)
            channels = int.from_bytes(wav_data[22:24], byteorder='little')
            if channels != 1:
                _LOGGER.warning("WAV file has %d channels, expected 1 (mono). Proceeding anyway...", channels)
            
            # Check sample rate (offset 24-27) - should be 8000 for G.711
            sample_rate = int.from_bytes(wav_data[24:28], byteorder='little')
            if sample_rate != 8000:
                _LOGGER.warning("WAV file sample rate is %d Hz, expected 8000 Hz. Proceeding anyway...", sample_rate)
            
            _LOGGER.info("Detected %s WAV file (%d channels, %d Hz)", codec_name, channels, sample_rate)
            
            # Find "data" chunk and extract raw audio
            # WAV format: chunks start at offset 12
            offset = 12
            while offset < len(wav_data) - 8:
                chunk_id = wav_data[offset:offset+4]
                chunk_size = int.from_bytes(wav_data[offset+4:offset+8], byteorder='little')
                
                # Validate chunk size - catch obviously invalid sizes (e.g., > 100MB for a small file)
                # Also check if it extends beyond file
                max_reasonable_size = len(wav_data) * 2  # Allow up to 2x file size (for padding)
                if chunk_size > max_reasonable_size or chunk_size < 0 or (offset + 8 + chunk_size) > len(wav_data):
                    # Invalid chunk size
                    if chunk_id == b'data':
                        # This is the data chunk - extract what's available
                        data_start = offset + 8
                        available_bytes = len(wav_data) - data_start
                        _LOGGER.debug(
                            "WAV file data chunk header claims %d bytes, but only %d bytes available in file. "
                            "Using available data (file may be truncated or header incorrect).",
                            chunk_size, available_bytes
                        )
                        raw_audio = wav_data[data_start:]
                        _LOGGER.info("Extracted %d bytes of raw G.711ulaw audio from WAV file (header was invalid)", len(raw_audio))
                        return raw_audio
                    else:
                        # Not the data chunk - invalid size means we can't calculate next offset
                        # Search for next chunk by looking for common chunk IDs
                        found_next = False
                        for search_offset in range(offset + 8, min(offset + 200, len(wav_data) - 8)):
                            if wav_data[search_offset:search_offset+4] in [b'data', b'fmt ', b'LIST', b'fact']:
                                offset = search_offset
                                found_next = True
                                break
                        if not found_next:
                            # Can't find next chunk - try to find 'data' anywhere in remaining file
                            data_pos = wav_data.find(b'data', offset + 8)
                            if data_pos != -1 and data_pos < len(wav_data) - 8:
                                offset = data_pos
                                continue
                            else:
                                # Give up - can't find data chunk
                                break
                        continue
                
                if chunk_id == b'data':
                    # Found data chunk - extract raw audio
                    data_start = offset + 8
                    data_end = data_start + chunk_size
                    raw_audio = wav_data[data_start:data_end]
                    _LOGGER.info("Extracted %d bytes of raw G.711ulaw audio from WAV file", len(raw_audio))
                    return raw_audio
                
                # Move to next chunk
                offset += 8 + chunk_size
                # Align to even boundary
                if offset % 2:
                    offset += 1
            
            # TODO: Fix WAV file parsing issues
            # Issues to address:
            # - Some WAV files have malformed headers or non-standard chunk ordering
            # - "Could not find 'data' chunk" error occurs with some valid WAV files
            # - Should use a proper WAV parsing library (e.g., wave module or scipy.io.wavfile)
            #   instead of manual byte parsing to handle edge cases
            _LOGGER.error("Could not find 'data' chunk in WAV file")
            return None
            
        except Exception as e:
            _LOGGER.error("Failed to extract G.711 from WAV: %s", e)
            return None
    
    async def async_media_stop(self) -> None:
        """Stop media playback."""
        if self._audio_session_id:
            self._audio_session_id = None
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
        
        # Home Assistant's async_browse_media only accepts hass and media_content_id
        # It will automatically filter and show available media sources
        return await async_browse_media(
            self.hass,
            media_content_id,
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
