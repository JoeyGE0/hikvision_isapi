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
        _LOGGER.info("=== STREAM AUDIO START ===")
        _LOGGER.info("media_id: %s, media_type: %s", media_id, media_type)
        try:
            # Get audio data
            _LOGGER.info("Step 1: Getting audio data...")
            audio_data = await self._get_audio_data(media_id, media_type)
            _LOGGER.info("Audio data result: %s bytes", len(audio_data) if audio_data else 0)
            if not audio_data:
                _LOGGER.error("Failed to get audio data")
                await self.async_media_stop()
                return
            
            # Convert to G.711ulaw
            _LOGGER.info("Step 2: Converting audio to G.711ulaw...")
            ulaw_data = await self.hass.async_add_executor_job(
                self._convert_to_ulaw, audio_data
            )
            _LOGGER.info("Ulaw conversion result: %s bytes", len(ulaw_data) if ulaw_data else 0)
            
            if not ulaw_data:
                _LOGGER.error("Failed to convert audio to G.711ulaw")
                await self.async_media_stop()
                return
            
            # Stream to camera
            _LOGGER.info("Step 3: Sending audio stream to camera...")
            await self.hass.async_add_executor_job(
                self._send_audio_stream, ulaw_data
            )
            _LOGGER.info("Audio stream sent")
            
            # Close session after streaming
            _LOGGER.info("Step 4: Closing session...")
            await self.async_media_stop()
            _LOGGER.info("=== STREAM AUDIO COMPLETE ===")
            
        except Exception as e:
            _LOGGER.error("Error streaming audio: %s", e, exc_info=True)
            await self.async_media_stop()
    
    async def _get_audio_data(self, media_id: str, media_type: str) -> bytes | None:
        """Get audio data from media_id (URL, TTS, or media-source)."""
        _LOGGER.info("=== GET AUDIO DATA START ===")
        _LOGGER.info("media_id: %s, media_type: %s", media_id, media_type)
        
        from homeassistant.components.media_source import (
            async_resolve_media,
            is_media_source_id,
        )
        
        try:
            # Handle media-source IDs first (includes TTS and local media)
            if is_media_source_id(media_id):
                _LOGGER.info("media_id is a media-source ID, resolving...")
                try:
                    resolved_media = await async_resolve_media(self.hass, media_id)
                    _LOGGER.info("Resolved media result: %s", resolved_media)
                    if resolved_media and resolved_media.url:
                        _LOGGER.info("Resolved media source: %s -> %s", media_id, resolved_media.url)
                        _LOGGER.info("Resolved URL type: %s", type(resolved_media.url))
                        
                        # Keep the full resolved URL (may contain auth tokens in query params)
                        full_resolved_url = resolved_media.url
                        _LOGGER.info("Full resolved URL (with query params): %s", full_resolved_url)
                        
                        # For filesystem access, use URL without query params
                        media_url = full_resolved_url.split("?")[0] if "?" in full_resolved_url else full_resolved_url
                        _LOGGER.info("Media URL (for filesystem lookup): %s", media_url)
                        
                        # For local media files, try filesystem first, then use resolved URL via HTTP
                        if media_url.startswith("/media/local/"):
                            _LOGGER.info("Detected /media/local/ path, attempting filesystem access")
                            media_path = media_url.replace("/media/local/", "")
                            _LOGGER.info("Extracted media path: %s", media_path)
                            
                            import os
                            def read_media_file():
                                config_dir = self.hass.config.config_dir
                                _LOGGER.info("Config directory: %s", config_dir)
                                # Home Assistant stores media files in the media/ directory
                                # Try multiple possible locations
                                possible_paths = [
                                    os.path.join(config_dir, "media", media_path),  # Standard location: config/media/filename
                                    os.path.join(config_dir, "www", media_path),     # Legacy location: config/www/filename
                                    os.path.join(config_dir, "media", "local", media_path),  # Alternative: config/media/local/filename
                                ]
                                _LOGGER.info("Trying filesystem paths: %s", possible_paths)
                                
                                for file_path in possible_paths:
                                    _LOGGER.info("Checking path: %s", file_path)
                                    _LOGGER.info("  - exists: %s", os.path.exists(file_path))
                                    if os.path.exists(file_path):
                                        _LOGGER.info("  - isfile: %s", os.path.isfile(file_path))
                                        if os.path.isfile(file_path):
                                            file_size = os.path.getsize(file_path)
                                            _LOGGER.info("  - size: %d bytes", file_size)
                                            _LOGGER.info("Reading media file from filesystem: %s", file_path)
                                            with open(file_path, 'rb') as f:
                                                data = f.read()
                                                _LOGGER.info("Read %d bytes from filesystem", len(data))
                                                return data
                                
                                # If not found, log all tried paths for debugging
                                _LOGGER.warning("Media file not found in filesystem. Tried paths: %s", possible_paths)
                                return None
                            
                            file_data = await self.hass.async_add_executor_job(read_media_file)
                            _LOGGER.info("Filesystem read result: %s bytes", len(file_data) if file_data else 0)
                            if file_data and len(file_data) > 0:
                                # Validate it's actually audio data
                                _LOGGER.info("Validating file data (first 100 bytes): %s", file_data[:100])
                                if file_data[:100].strip().startswith(b'<'):
                                    _LOGGER.error("File appears to be HTML/text, not audio")
                                    return None
                                _LOGGER.info("File data validated, returning %d bytes", len(file_data))
                                return file_data
                            else:
                                _LOGGER.warning("No file data from filesystem, will try HTTP")
                            
                            # File not found in filesystem - use the full resolved URL (with query params) via HTTP
                            _LOGGER.info("=== FILESYSTEM NOT FOUND, TRYING HTTP ===")
                            _LOGGER.info("Full resolved URL: %s", full_resolved_url)
                            
                            # Use the full resolved URL which may include auth tokens
                            if full_resolved_url.startswith("http://") or full_resolved_url.startswith("https://"):
                                # Already a full URL
                                full_url = full_resolved_url
                                _LOGGER.info("URL is already full URL")
                            else:
                                # Relative URL, prepend base URL
                                base_url = self.hass.config.internal_url or self.hass.config.external_url or "http://localhost:8123"
                                _LOGGER.info("Base URL (internal: %s, external: %s): %s", 
                                           self.hass.config.internal_url, 
                                           self.hass.config.external_url,
                                           base_url)
                                base_url = base_url.rstrip("/")
                                full_url = f"{base_url}{full_resolved_url}"
                            
                            _LOGGER.info("Final HTTP URL: %s", full_url)
                            _LOGGER.info("Creating authenticated session...")
                            
                            # Use Home Assistant's authenticated session
                            session = async_get_clientsession(self.hass)
                            _LOGGER.info("Session created, making GET request...")
                            try:
                                async with session.get(full_url, timeout=30, allow_redirects=True) as response:
                                    _LOGGER.info("HTTP Response status: %s", response.status)
                                    _LOGGER.info("HTTP Response headers: %s", dict(response.headers))
                                    
                                    if response.status == 401:
                                        _LOGGER.error("Authentication failed for media URL: %s", full_url)
                                        response_text = await response.text()
                                        _LOGGER.error("Response body: %s", response_text[:500])
                                        return None
                                    if response.status == 404:
                                        _LOGGER.error("Media file not found at URL: %s", full_url)
                                        response_text = await response.text()
                                        _LOGGER.error("Response body: %s", response_text[:500])
                                        return None
                                    
                                    _LOGGER.info("Response status OK, reading data...")
                                    response.raise_for_status()
                                    
                                    http_data = await response.read()
                                    _LOGGER.info("Read %d bytes from HTTP response", len(http_data) if http_data else 0)
                                    
                                    if http_data and len(http_data) > 100:
                                        # Validate it's actually audio, not HTML error page
                                        _LOGGER.info("Validating HTTP data (first 100 bytes): %s", http_data[:100])
                                        if http_data[:100].strip().startswith(b'<'):
                                            _LOGGER.error("Received HTML error page instead of audio file")
                                            _LOGGER.error("Response preview: %s", http_data[:500].decode('utf-8', errors='ignore'))
                                            return None
                                        _LOGGER.info("HTTP data validated, returning %d bytes", len(http_data))
                                        return http_data
                                    else:
                                        _LOGGER.error("Downloaded data is empty or too small: %d bytes", len(http_data) if http_data else 0)
                                        return None
                            except Exception as e:
                                _LOGGER.error("Failed to download media via HTTP: %s", e, exc_info=True)
                                return None
                        
                        # For other relative URLs (not /media/local/), download via HTTP
                        if media_url.startswith("/"):
                            base_url = self.hass.config.internal_url or self.hass.config.external_url or "http://localhost:8123"
                            base_url = base_url.rstrip("/")
                            full_url = f"{base_url}{full_resolved_url}"  # Use full URL with query params
                            _LOGGER.info("Downloading media via HTTP: %s", full_url)
                            
                            session = async_get_clientsession(self.hass)
                            try:
                                async with session.get(full_url, timeout=30, allow_redirects=True) as response:
                                    if response.status == 401:
                                        _LOGGER.error("Authentication failed for media URL")
                                        return None
                                    response.raise_for_status()
                                    return await response.read()
                            except Exception as e:
                                _LOGGER.error("Failed to download media: %s", e)
                                return None
                        
                        if not full_resolved_url.startswith("http://") and not full_resolved_url.startswith("https://"):
                            _LOGGER.error("Invalid URL format: %s", full_resolved_url)
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
        """Convert audio to G.711ulaw format using ffmpeg directly.
        
        This method uses ffmpeg via subprocess for reliable conversion,
        avoiding pydub's format detection issues.
        """
        _LOGGER.info("=== CONVERT TO ULAW START ===")
        _LOGGER.info("Input audio data size: %d bytes", len(audio_data) if audio_data else 0)
        
        if not audio_data or len(audio_data) == 0:
            _LOGGER.error("Audio data is empty or None")
            return None
        
        if len(audio_data) < 100:
            _LOGGER.error("Audio data too small (%d bytes), likely invalid", len(audio_data))
            return None
        
        # Validate it's actually audio data, not HTML/text
        _LOGGER.info("First 100 bytes (hex): %s", audio_data[:100].hex())
        _LOGGER.info("First 100 bytes (ascii preview): %s", audio_data[:100].decode('utf-8', errors='replace')[:100])
        
        if audio_data[:100].strip().startswith(b'<'):
            _LOGGER.error("Received HTML/text instead of audio data (likely error page)")
            _LOGGER.error("Data preview: %s", audio_data[:500].decode('utf-8', errors='ignore'))
            return None
        
        # Check for valid audio file signatures
        _LOGGER.info("Checking audio file signatures...")
        is_valid_audio = (
            audio_data.startswith(b'ID3') or  # MP3 with ID3 tag
            audio_data.startswith(b'\xff\xfb') or  # MP3 frame sync
            audio_data.startswith(b'\xff\xf3') or  # MP3 frame sync
            audio_data.startswith(b'\xff\xf2') or  # MP3 frame sync
            audio_data.startswith(b'RIFF') or  # WAV
            audio_data.startswith(b'\x00\x00\x00\x20ftyp') or  # M4A/MP4
            audio_data.startswith(b'OggS') or  # OGG
            audio_data.startswith(b'fLaC') or  # FLAC
            b'ftyp' in audio_data[:20]  # MP4/M4A (ftyp can be at offset 4)
        )
        
        _LOGGER.info("Valid audio signature detected: %s", is_valid_audio)
        if not is_valid_audio:
            _LOGGER.warning("Audio data doesn't have recognized audio file signature, but attempting conversion anyway")
        
        import subprocess
        import tempfile
        import os
        
        _LOGGER.info("Creating temporary files for ffmpeg conversion...")
        # Write input to temporary file
        input_fd, input_path = tempfile.mkstemp(suffix='.audio')
        output_fd, output_path = tempfile.mkstemp(suffix='.ulaw')
        _LOGGER.info("Input temp file: %s", input_path)
        _LOGGER.info("Output temp file: %s", output_path)
        
        try:
            # Write input audio data
            _LOGGER.info("Writing %d bytes to input temp file...", len(audio_data))
            with os.fdopen(input_fd, 'wb') as f:
                f.write(audio_data)
            _LOGGER.info("Input file written successfully")
            
            # Verify file was written
            input_size = os.path.getsize(input_path)
            _LOGGER.info("Input file size: %d bytes", input_size)
            
            # Use ffmpeg to convert directly to G.711ulaw (mulaw)
            # Command: ffmpeg -i input -ar 8000 -ac 1 -acodec pcm_mulaw output
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ar', '8000',      # Sample rate 8000Hz
                '-ac', '1',         # Mono channel
                '-acodec', 'pcm_mulaw',  # G.711ulaw codec
                '-f', 'mulaw',      # Format: mulaw
                '-y',               # Overwrite output
                output_path
            ]
            
            _LOGGER.info("Running ffmpeg conversion command: %s", ' '.join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                timeout=30
            )
            
            _LOGGER.info("ffmpeg return code: %d", result.returncode)
            if result.stdout:
                _LOGGER.info("ffmpeg stdout: %s", result.stdout.decode('utf-8', errors='ignore')[:500])
            if result.stderr:
                _LOGGER.info("ffmpeg stderr: %s", result.stderr.decode('utf-8', errors='ignore')[:1000])
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                _LOGGER.error("ffmpeg conversion failed (code %d): %s", result.returncode, error_msg)
                return None
            
            # Read output file
            _LOGGER.info("Reading output file...")
            with os.fdopen(output_fd, 'rb') as f:
                ulaw_data = f.read()
            
            _LOGGER.info("Output file size: %d bytes", len(ulaw_data) if ulaw_data else 0)
            
            if not ulaw_data or len(ulaw_data) == 0:
                _LOGGER.error("ffmpeg produced empty output")
                return None
            
            _LOGGER.info("Successfully converted %d bytes audio to %d bytes G.711ulaw", len(audio_data), len(ulaw_data))
            return ulaw_data
            
        except subprocess.TimeoutExpired:
            _LOGGER.error("ffmpeg conversion timed out after 30 seconds")
            return None
        except FileNotFoundError:
            _LOGGER.error("ffmpeg not found. Please ensure ffmpeg is installed and in PATH")
            return None
        except Exception as e:
            _LOGGER.error("Failed to convert audio to G.711ulaw: %s", e, exc_info=True)
            return None
        finally:
            # Clean up temporary files
            _LOGGER.info("Cleaning up temporary files...")
            try:
                if os.path.exists(input_path):
                    os.unlink(input_path)
                    _LOGGER.info("Deleted input temp file: %s", input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
                    _LOGGER.info("Deleted output temp file: %s", output_path)
            except Exception as e:
                _LOGGER.warning("Failed to clean up temp files: %s", e)
            _LOGGER.info("=== CONVERT TO ULAW END ===")
    
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
