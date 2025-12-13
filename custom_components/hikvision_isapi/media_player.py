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

    entities = [
        HikvisionMediaPlayer(coordinator, api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionMediaPlayer(MediaPlayerEntity):
    """Media player entity for Hikvision camera speaker.
    
    Supports only pre-encoded G.711ulaw audio files:
    - WAV files with G.711ulaw codec (8kHz, mono)
    - Raw G.711ulaw files (.ulaw, .pcm)
    
    No audio conversion is performed - files must already be in G.711ulaw format.
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

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
        try:
            audio_data = self.api.get_two_way_audio()
            if not audio_data or not audio_data.get("enabled", False):
                # Enable it - always set enabled=true to ensure it's on
                import xml.etree.ElementTree as ET
                XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
                
                # Get current values or use defaults
                compression = audio_data.get('audioCompressionType', 'G.711ulaw') if audio_data else 'G.711ulaw'
                speaker_vol = audio_data.get('speakerVolume', 100) if audio_data else 100
                mic_vol = audio_data.get('microphoneVolume', 100) if audio_data else 100
                
                xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>true</enabled>
<audioCompressionType>{compression}</audioCompressionType>
<speakerVolume>{speaker_vol}</speakerVolume>
<microphoneVolume>{mic_vol}</microphoneVolume>
<noisereduce>true</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
                
                url = f"http://{self.api.host}/ISAPI/System/TwoWayAudio/channels/1"
                response = requests.put(
                    url,
                    auth=(self.api.username, self.api.password),
                    data=xml_data,
                    headers={"Content-Type": "application/xml"},
                    verify=False,
                    timeout=5
                )
                response.raise_for_status()
                _LOGGER.info("Two-way audio enabled (enabled=true, speakerVolume=%d)", speaker_vol)
            else:
                _LOGGER.debug("Two-way audio already enabled")
        except Exception as e:
            _LOGGER.error("Failed to enable two-way audio: %s", e)
    
    async def _stream_audio(self, media_id: str, media_type: str):
        """Stream audio to camera."""
        try:
            # Get audio data
            audio_data = await self._get_audio_data(media_id, media_type)
            if not audio_data:
                _LOGGER.error("Failed to get audio data for: %s", media_id)
                await self.async_media_stop()
                return
            
            # Extract G.711ulaw data (no conversion - must be pre-encoded)
            ulaw_data = await self.hass.async_add_executor_job(
                self._extract_ulaw_data, audio_data, media_id
            )
            
            if not ulaw_data:
                _LOGGER.error("File is not in G.711ulaw format. Only pre-encoded G.711ulaw WAV files or raw ulaw files are supported.")
                await self.async_media_stop()
                return
            
            # Stream to camera
            await self.hass.async_add_executor_job(
                self._send_audio_stream, ulaw_data
            )
            
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
    
    def _extract_ulaw_data(self, audio_data: bytes, media_id: str = "") -> bytes | None:
        """Extract G.711ulaw audio data from file.
        
        Supports:
        - WAV files with G.711ulaw codec (codec ID 0x0007)
        - Raw G.711ulaw files (no header)
        
        Returns raw ulaw audio data (no WAV header) or None if format is not supported.
        """
        if len(audio_data) < 12:
            _LOGGER.error("File too small to be valid audio")
            return None
        
        # Check if it's a WAV file (starts with "RIFF" and "WAVE")
        if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
            return self._extract_ulaw_from_wav(audio_data)
        
        # Check file extension for raw ulaw files
        if media_id:
            media_lower = media_id.lower()
            if media_lower.endswith('.ulaw') or media_lower.endswith('.pcm'):
                _LOGGER.info("Treating as raw G.711ulaw file")
                return audio_data
        
        # If it's not a WAV and not a known raw format, try to detect if it's raw ulaw
        # (no header, just raw data - this is a guess)
        if len(audio_data) > 1000:  # Reasonable size for audio
            _LOGGER.warning("File doesn't appear to be WAV or raw ulaw. Attempting as raw ulaw...")
            return audio_data
        
        _LOGGER.error("Unsupported audio format. Only G.711ulaw WAV files or raw ulaw files are supported.")
        return None
    
    def _extract_ulaw_from_wav(self, wav_data: bytes) -> bytes | None:
        """Extract raw G.711ulaw audio data from WAV file.
        
        WAV format:
        - Offset 0-3: "RIFF"
        - Offset 8-11: "WAVE"
        - Offset 20-21: Audio format code (0x0007 = G.711ulaw, 0x0006 = G.711alaw)
        - Offset 22-23: Number of channels (should be 1 for mono)
        - Offset 24-27: Sample rate (should be 8000 for G.711)
        - After "data" chunk: Raw audio data
        """
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
                _LOGGER.error("File is G.711alaw, but camera requires G.711ulaw")
                return None
            else:
                _LOGGER.error("WAV file is not G.711ulaw format (codec: 0x%04x). Only G.711ulaw (0x0007) is supported.", audio_format)
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
                
                if chunk_id == b'data':
                    # Found data chunk - extract raw audio
                    data_start = offset + 8
                    
                    # Validate chunk size - if it's unreasonably large or extends beyond file, use available data
                    if chunk_size > len(wav_data) or (data_start + chunk_size) > len(wav_data):
                        # WAV header says there's more data than exists - file might be truncated or header is wrong
                        available_bytes = len(wav_data) - data_start
                        _LOGGER.warning(
                            "WAV file data chunk header claims %d bytes, but only %d bytes available in file. "
                            "Using available data (file may be truncated or header incorrect).",
                            chunk_size, available_bytes
                        )
                        data_end = len(wav_data)
                    else:
                        data_end = data_start + chunk_size
                    
                    raw_audio = wav_data[data_start:data_end]
                    _LOGGER.info("Extracted %d bytes of raw G.711ulaw audio from WAV file", len(raw_audio))
                    return raw_audio
                
                # Move to next chunk
                offset += 8 + chunk_size
                # Align to even boundary
                if offset % 2:
                    offset += 1
            
            _LOGGER.error("Could not find 'data' chunk in WAV file")
            return None
            
        except Exception as e:
            _LOGGER.error("Failed to extract ulaw from WAV: %s", e)
            return None
    
    def _send_audio_stream(self, ulaw_data: bytes):
        """Send audio stream to camera using HTTP chunked transfer encoding.
        
        Uses a single PUT request with Transfer-Encoding: chunked to stream audio data
        at the correct rate (8000 bytes/sec for G.711ulaw). This allows for live streaming
        and future features like start/stop controls.
        """
        session_id = None
        try:
            # Ensure two-way audio is enabled
            self._enable_two_way_audio()
            
            # Open audio session first
            session_id = self.api.open_audio_session()
            if not session_id:
                _LOGGER.error("Failed to open audio session")
                return
            
            _LOGGER.info("Opened audio session: %s", session_id)
            
            # Use the audioData endpoint with PUT
            # According to ISAPI PDF: sessionId is a query parameter (required for multi-channel, optional for single channel)
            endpoint = f"http://{self.api.host}/ISAPI/System/TwoWayAudio/channels/1/audioData?sessionId={session_id}"
            _LOGGER.debug("Using audioData endpoint: %s", endpoint)
            
            # Chunk size: 160 bytes = 20ms of audio at 8kHz (8000 bytes/sec)
            # G.711ulaw: 1 byte per sample, 8000 samples/sec = 8000 bytes/sec
            # 160 bytes / 8000 bytes/sec = 0.02 seconds = 20ms per chunk
            chunk_size = 160
            sleep_time = 0.02  # 20ms delay to maintain 8000 bytes/sec rate
            import time
            
            # Generator function to yield chunks with proper timing
            def chunk_generator():
                """Generator that yields audio chunks with proper timing for streaming."""
                total_chunks = (len(ulaw_data) + chunk_size - 1) // chunk_size
                _LOGGER.info("Streaming %d bytes in %d chunks (%.2f seconds of audio)", 
                            len(ulaw_data), total_chunks, len(ulaw_data) / 8000.0)
                
                sent_bytes = 0
                for i in range(0, len(ulaw_data), chunk_size):
                    chunk = ulaw_data[i:i + chunk_size]
                    
                    # Pad chunk to exact size if needed (last chunk might be smaller)
                    if len(chunk) < chunk_size:
                        chunk = chunk + (b'\x7F' * (chunk_size - len(chunk)))  # 0x7F is silence in ulaw
                    
                    yield chunk
                    sent_bytes += len(chunk)
                    
                    # Log progress every second (50 chunks)
                    if (i // chunk_size) % 50 == 0 and i > 0:
                        _LOGGER.debug("Streamed %d bytes (%.1f%%)", sent_bytes, 
                                     (sent_bytes / len(ulaw_data)) * 100)
                    
                    # Wait 20ms before next chunk to maintain proper playback rate
                    # Only sleep if not the last chunk
                    if i + chunk_size < len(ulaw_data):
                        time.sleep(sleep_time)
                
                _LOGGER.info("Audio streaming complete: sent %d bytes", sent_bytes)
            
            # Create a session for persistent connection
            session = requests.Session()
            session.auth = (self.api.username, self.api.password)
            session.verify = False
            
            # Send audio using chunked transfer encoding in a single request
            # Transfer-Encoding: chunked allows streaming without Content-Length
            try:
                response = session.put(
                    endpoint,
                    data=chunk_generator(),
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Transfer-Encoding": "chunked"  # Enable HTTP chunked transfer encoding
                    },
                    timeout=30,  # Longer timeout for streaming (allows time for all chunks)
                    stream=True  # Don't wait for response body immediately
                )
                
                # Check status code
                status_code = response.status_code
                if status_code == 200:
                    _LOGGER.info("Audio stream sent successfully (status 200)")
                else:
                    # Try to read error response
                    error_text = 'No response body'
                    try:
                        if response.headers.get('Content-Length', '0') != '0':
                            error_text = response.text[:200]
                    except:
                        pass
                    _LOGGER.warning("Camera returned status %d: %s", status_code, error_text)
                
                # Close response
                response.close()
                
            except requests.exceptions.Timeout:
                _LOGGER.warning("Timeout during audio streaming (camera may still be processing)")
            except requests.exceptions.HTTPError as e:
                _LOGGER.error("HTTP error during audio streaming: %s", e)
            except Exception as e:
                _LOGGER.error("Error during audio streaming: %s", e, exc_info=True)
            finally:
                session.close()
            
            # Small delay before closing session to let camera process final chunks
            time.sleep(0.1)
                
        except Exception as e:
            _LOGGER.error("Failed to send audio stream: %s", e)
        finally:
            # Always close the session
            if session_id:
                try:
                    self.api.close_audio_session()
                    _LOGGER.info("Closed audio session")
                except Exception as e:
                    _LOGGER.warning("Failed to close audio session: %s", e)

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

    async def async_media_stop(self) -> None:
        """Stop media playback."""
        if self._audio_session_id:
            # Try to close session if method exists
            try:
                await self.hass.async_add_executor_job(
                    self.api.close_audio_session
                )
            except Exception:
                pass  # Close might not be needed
            
            self._audio_session_id = None
            self.async_write_ha_state()

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
