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
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

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
            if not audio_data.get("enabled", False):
                # Enable it
                import xml.etree.ElementTree as ET
                XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"
                
                xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>true</enabled>
<audioCompressionType>{audio_data.get('audioCompressionType', 'G.711ulaw')}</audioCompressionType>
<speakerVolume>{audio_data.get('speakerVolume', 50)}</speakerVolume>
<microphoneVolume>{audio_data.get('microphoneVolume', 100)}</microphoneVolume>
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
                        
                        # Convert relative URL to full URL if needed
                        media_url = resolved_media.url
                        if media_url.startswith("/"):
                            # Relative URL - need to use Home Assistant's internal URL
                            base_url = self.hass.config.internal_url or self.hass.config.external_url
                            if not base_url:
                                _LOGGER.error("No Home Assistant URL configured")
                                return None
                            # Remove trailing slash from base_url if present
                            base_url = base_url.rstrip("/")
                            media_url = f"{base_url}{resolved_media.url}"
                            _LOGGER.info("Converted to full URL: %s", media_url)
                        
                        # Download from resolved URL
                        # Use Home Assistant's internal request if it's a local URL
                        if media_url.startswith("http://") or media_url.startswith("https://"):
                            response = await self.hass.async_add_executor_job(
                                requests.get, media_url, {"timeout": 30}
                            )
                        else:
                            # Try using Home Assistant's built-in method for local media
                            from homeassistant.components.media_source import async_resolve_media
                            # For local media, we might need to use a different approach
                            # Try accessing via the internal URL
                            internal_url = self.hass.config.internal_url or "http://localhost:8123"
                            full_url = f"{internal_url.rstrip('/')}{resolved_media.url}"
                            response = await self.hass.async_add_executor_job(
                                requests.get, full_url, {"timeout": 30}
                            )
                        response.raise_for_status()
                        return response.content
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
                            if base_url:
                                base_url = base_url.rstrip("/")
                                media_url = f"{base_url}{resolved_media.url}"
                        
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
            
            # Export as raw PCM 16-bit
            pcm_data = io.BytesIO()
            audio.export(pcm_data, format="raw", parameters=["-acodec", "pcm_s16le"])
            pcm_bytes = pcm_data.getvalue()
            
            # Convert PCM to G.711ulaw using audioop
            try:
                import audioop
                ulaw_data = audioop.lin2ulaw(pcm_bytes, 2)  # 2 = 16-bit
                return ulaw_data
            except ImportError:
                # audioop not available, try alternative
                _LOGGER.warning("audioop not available, using pydub export")
                # Export directly as ulaw using ffmpeg (if available via pydub)
                ulaw_io = io.BytesIO()
                audio.export(ulaw_io, format="ulaw")
                return ulaw_io.getvalue()
            
        except Exception as e:
            _LOGGER.error("Failed to convert audio: %s", e)
            return None
    
    def _send_audio_stream(self, ulaw_data: bytes):
        """Send audio stream to camera.
        
        Based on Stack Overflow findings: Must send at correct rate (8000 bytes/sec for G.711ulaw).
        For 160-byte chunks, delay 20ms between chunks to maintain proper playback speed.
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
            endpoint = f"http://{self.api.host}/ISAPI/System/TwoWayAudio/channels/1/audioData"
            
            # Chunk size: 160 bytes = 20ms of audio at 8kHz (8000 bytes/sec)
            # G.711ulaw: 1 byte per sample, 8000 samples/sec = 8000 bytes/sec
            # 160 bytes / 8000 bytes/sec = 0.02 seconds = 20ms per chunk
            chunk_size = 160
            sleep_time = 0.02  # 20ms delay to maintain 8000 bytes/sec rate
            import time
            
            # Create a session for persistent connection (more efficient than individual requests)
            session = requests.Session()
            session.auth = (self.api.username, self.api.password)
            session.verify = False
            
            # Send audio in chunks with proper timing
            total_chunks = (len(ulaw_data) + chunk_size - 1) // chunk_size
            _LOGGER.info("Streaming %d bytes in %d chunks (%.2f seconds of audio)", 
                        len(ulaw_data), total_chunks, len(ulaw_data) / 8000.0)
            
            for i in range(0, len(ulaw_data), chunk_size):
                chunk = ulaw_data[i:i + chunk_size]
                
                # Pad chunk to exact size if needed (last chunk might be smaller)
                if len(chunk) < chunk_size:
                    chunk = chunk + (b'\xff' * (chunk_size - len(chunk)))
                
                try:
                    response = session.put(
                        endpoint,
                        data=chunk,
                        headers={
                            "Content-Type": "audio/G711-ulaw",
                        },
                        timeout=5
                    )
                    
                    if response.status_code in [200, 204]:
                        # Success, wait before next chunk to maintain proper playback rate
                        time.sleep(sleep_time)
                    else:
                        _LOGGER.warning("Audio streaming failed with status %d: %s", 
                                       response.status_code, response.text[:100])
                        break
                except Exception as e:
                    _LOGGER.error("Error sending audio chunk: %s", e)
                    break
            else:
                # Successfully sent all chunks
                _LOGGER.info("Audio streamed successfully")
            
            session.close()
                
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

