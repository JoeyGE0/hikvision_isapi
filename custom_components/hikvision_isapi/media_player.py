"""Media player platform for Hikvision ISAPI."""
import asyncio
import logging
import io
from typing import Any
from urllib.parse import urlparse

import requests
from pydub import AudioSegment

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
    BrowseMedia,
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
    """Media player entity for Hikvision camera speaker."""

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
                _LOGGER.error("Failed to get audio data")
                await self.async_media_stop()
                return
            
            # Convert to G.711ulaw
            ulaw_data = await self.hass.async_add_executor_job(
                self._convert_to_ulaw, audio_data
            )
            
            if not ulaw_data:
                _LOGGER.error("Failed to convert audio to G.711ulaw")
                await self.async_media_stop()
                return
            
            # Stream to camera
            await self.hass.async_add_executor_job(
                self._send_audio_stream, ulaw_data
            )
            
            # Close session after streaming
            await self.async_media_stop()
            
        except Exception as e:
            _LOGGER.error("Error streaming audio: %s", e)
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
                    resolved_media = await async_resolve_media(self.hass, media_id)
                    if resolved_media and resolved_media.url:
                        _LOGGER.info("Resolved media source: %s -> %s", media_id, resolved_media.url)
                        
                        # Use the resolved URL - for local media, read directly from filesystem
                        media_url = resolved_media.url
                        
                        # Remove any query parameters
                        if "?" in media_url:
                            media_url = media_url.split("?")[0]
                        
                        # For local media files, read directly from filesystem
                        if media_url.startswith("/media/local/"):
                            media_path = media_url.replace("/media/local/", "")
                            
                            import os
                            def read_media_file():
                                config_dir = self.hass.config.config_dir
                                # Home Assistant stores media files in the media/ directory
                                # Try multiple possible locations
                                possible_paths = [
                                    os.path.join(config_dir, "media", media_path),  # Standard location: config/media/filename
                                    os.path.join(config_dir, "www", media_path),     # Legacy location: config/www/filename
                                    os.path.join(config_dir, "media", "local", media_path),  # Alternative: config/media/local/filename
                                ]
                                
                                for file_path in possible_paths:
                                    if os.path.exists(file_path) and os.path.isfile(file_path):
                                        _LOGGER.info("Reading media file from filesystem: %s", file_path)
                                        with open(file_path, 'rb') as f:
                                            return f.read()
                                
                                # If not found, log all tried paths for debugging
                                _LOGGER.error("Media file not found in filesystem. Tried paths: %s", possible_paths)
                                _LOGGER.error("Config directory: %s, Media path: %s", config_dir, media_path)
                                return None
                            
                            file_data = await self.hass.async_add_executor_job(read_media_file)
                            if file_data:
                                return file_data
                            
                            # Don't try HTTP for local files - if not in filesystem, it won't work via HTTP either
                            # (HTTP requires auth and the file should be accessible via filesystem)
                            _LOGGER.error("Local media file not found. Please ensure the file exists in your Home Assistant media directory.")
                            return None
                        
                        # For other relative URLs, convert to full URL and download
                        if media_url.startswith("/"):
                            base_url = self.hass.config.internal_url or self.hass.config.external_url or "http://localhost:8123"
                            base_url = base_url.rstrip("/")
                            media_url = f"{base_url}{media_url}"
                            _LOGGER.info("Downloading media via HTTP: %s", media_url)
                        
                        if not media_url.startswith("http://") and not media_url.startswith("https://"):
                            _LOGGER.error("Invalid URL: %s", media_url)
                            return None
                        
                        # Download via HTTP with authenticated session
                        session = async_get_clientsession(self.hass)
                        try:
                            async with session.get(media_url, timeout=30) as response:
                                if response.status == 401:
                                    _LOGGER.error("Authentication failed for media URL")
                                    return None
                                response.raise_for_status()
                                return await response.read()
                        except Exception as e:
                            _LOGGER.error("Failed to download media: %s", e)
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
    
    def _convert_to_ulaw(self, audio_data: bytes) -> bytes | None:
        """Convert audio to G.711ulaw format."""
        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to mono, 8000Hz (G.711 requirements)
            audio = audio.set_channels(1).set_frame_rate(8000)
            
            # Export as raw PCM 16-bit using s16le format (correct for pydub)
            pcm_data = io.BytesIO()
            audio.export(pcm_data, format="s16le")
            pcm_bytes = pcm_data.getvalue()
            
            # Convert PCM to G.711ulaw using audioop
            try:
                import audioop
                ulaw_data = audioop.lin2ulaw(pcm_bytes, 2)  # 2 = 16-bit
                return ulaw_data
            except ImportError:
                # audioop not available, use ffmpeg directly via pydub
                _LOGGER.warning("audioop not available, using ffmpeg to export as ulaw")
                ulaw_io = io.BytesIO()
                # Export directly as mulaw (G.711ulaw) using ffmpeg
                audio.export(ulaw_io, format="mulaw", parameters=["-ar", "8000", "-ac", "1"])
                return ulaw_io.getvalue()
            
        except Exception as e:
            _LOGGER.error("Failed to convert audio: %s", e, exc_info=True)
            return None
    
    def _send_audio_stream(self, ulaw_data: bytes):
        """Send audio stream to camera.
        
        Working sequence (tested and confirmed):
        1. Close any existing sessions
        2. Enable two-way audio
        3. Open a new session
        4. Send ALL audio in ONE request (not chunks!)
        5. Close session
        
        Note: The camera may timeout on the response, but the audio is sent successfully.
        The timeout error is expected and indicates success.
        """
        session_id = None
        import time
        
        try:
            # Step 1: Close any existing sessions first
            try:
                self.api.close_audio_session()
                time.sleep(0.5)
            except Exception:
                pass  # Ignore if no session exists
            
            # Step 2: Enable two-way audio
            self._enable_two_way_audio()
            time.sleep(0.5)
            
            # Step 3: Open audio session
            session_id = self.api.open_audio_session()
            if not session_id:
                _LOGGER.error("Failed to open audio session")
                return
            
            _LOGGER.info("Opened audio session: %s", session_id)
            
            # Step 4: Send ALL audio in ONE request (this is what works!)
            endpoint = f"http://{self.api.host}/ISAPI/System/TwoWayAudio/channels/1/audioData"
            _LOGGER.info("Sending %d bytes (%.2f seconds of audio) in one request", 
                        len(ulaw_data), len(ulaw_data) / 8000.0)
            
            try:
                # Send entire audio file at once - camera processes it and may timeout on response
                response = requests.put(
                    endpoint,
                    auth=(self.api.username, self.api.password),
                    data=bytes(ulaw_data),
                    verify=False,
                    timeout=10
                )
                _LOGGER.info("Audio sent, response status: %s", response.status_code)
            except requests.exceptions.ReadTimeout:
                # Timeout is expected and means success - camera is processing audio
                _LOGGER.info("Audio sent successfully (camera processing, timeout expected)")
            except requests.exceptions.ConnectionError as e:
                if "Read timed out" in str(e) or "timed out" in str(e).lower():
                    # This is actually success - camera received and is processing the audio
                    _LOGGER.info("Audio sent successfully (camera processing, timeout expected)")
                else:
                    _LOGGER.warning("Connection error (may still be success): %s", e)
                
        except Exception as e:
            _LOGGER.error("Failed to send audio stream: %s", e)
        finally:
            # Step 5: Always close the session
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
        """Browse media."""
        from homeassistant.components.media_source import async_browse_media
        
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
