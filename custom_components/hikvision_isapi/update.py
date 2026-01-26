"""Update platform for Hikvision ISAPI."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
import re

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import aiohttp

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# GitHub raw URLs for firmware archive
FIRMWARE_ARCHIVE_BASE = "https://raw.githubusercontent.com/JoeyGE0/hikvision-fw-archive/main"
FIRMWARES_LIVE_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_live.json"
FIRMWARES_MANUAL_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_manual.json"

# Update interval: check for firmware updates every 6 hours (archive updates twice daily)
UPDATE_INTERVAL = timedelta(hours=6)


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string into tuple for comparison.
    
    Examples:
        "5.7.23" -> (5, 7, 23)
        "5.5.820" -> (5, 5, 820)
        "1.3.4" -> (1, 3, 4)
    """
    if not version_str:
        return (0,)
    
    # Remove any non-numeric characters except dots
    version_str = re.sub(r'[^\d.]', '', str(version_str))
    
    try:
        parts = [int(x) for x in version_str.split('.') if x]
        return tuple(parts) if parts else (0,)
    except (ValueError, AttributeError):
        return (0,)


def compare_versions(current: str, available: str) -> bool:
    """Compare version strings. Returns True if available is newer than current."""
    current_tuple = parse_version(current)
    available_tuple = parse_version(available)
    
    # Compare tuples element by element
    max_len = max(len(current_tuple), len(available_tuple))
    current_padded = current_tuple + (0,) * (max_len - len(current_tuple))
    available_padded = available_tuple + (0,) * (max_len - len(available_tuple))
    
    return available_padded > current_padded


def normalize_model(model: str) -> str:
    """Normalize model name for matching.
    
    Removes common suffixes and variations to match firmware archive entries.
    Examples:
        "DS-2CD1043G0-I" -> "DS-2CD1043G0-I"
        "DS-2CD1043G0-IUF(2.8mm)" -> "DS-2CD1043G0-IUF"
    """
    if not model:
        return ""
    
    # Remove common suffixes in parentheses
    model = re.sub(r'\([^)]*\)', '', model).strip()
    
    # Remove trailing spaces and common suffixes
    model = model.strip()
    
    return model


class FirmwareUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching firmware update information."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        device_model: str,
        current_firmware: str,
        hardware_version: str | None = None,
    ) -> None:
        """Initialize the firmware update coordinator."""
        self.device_model = device_model
        self.current_firmware = current_firmware
        self.hardware_version = hardware_version
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_firmware_update_{device_model}",
            update_interval=UPDATE_INTERVAL,
        )
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch firmware update data from GitHub archive."""
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch both live and manual firmware lists
                async with session.get(FIRMWARES_LIVE_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        live_firmwares = await response.json()
                    else:
                        _LOGGER.warning("Failed to fetch live firmwares: HTTP %s", response.status)
                        live_firmwares = {}
                
                async with session.get(FIRMWARES_MANUAL_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        manual_firmwares = await response.json()
                    else:
                        _LOGGER.warning("Failed to fetch manual firmwares: HTTP %s", response.status)
                        manual_firmwares = {}
            
            # Combine firmware lists - GitHub JSON structure is flat dict with keys like "DS-2CD1043G0-I_UNKNOWN_5.7.23"
            # Each value is a dict with: model, version, download_url, date, supported_models, etc.
            all_firmwares = {}
            
            def process_firmware_dict(firmware_dict: dict) -> None:
                """Process firmware entries from GitHub JSON format."""
                if not isinstance(firmware_dict, dict):
                    return
                
                for key, entry in firmware_dict.items():
                    if not isinstance(entry, dict):
                        continue
                    
                    # Get model from entry (primary field)
                    model = entry.get("model", "")
                    if not model:
                        continue
                    
                    # Also check supported_models array for additional matches
                    supported_models = entry.get("supported_models", [])
                    if not isinstance(supported_models, list):
                        supported_models = []
                    
                    # Add to all_firmwares keyed by model
                    if model not in all_firmwares:
                        all_firmwares[model] = []
                    all_firmwares[model].append(entry)
                    
                    # Also add to supported_models entries
                    for supported_model in supported_models:
                        if supported_model and supported_model != model:
                            if supported_model not in all_firmwares:
                                all_firmwares[supported_model] = []
                            all_firmwares[supported_model].append(entry)
            
            # Process live firmwares
            process_firmware_dict(live_firmwares)
            
            # Process manual firmwares
            process_firmware_dict(manual_firmwares)
            
            # Find matching firmware for this device
            normalized_model = normalize_model(self.device_model)
            matching_firmwares = []
            
            # Try exact match first
            if normalized_model in all_firmwares:
                matching_firmwares = all_firmwares[normalized_model]
            else:
                # Try partial match (e.g., "DS-2CD1043G0" matches "DS-2CD1043G0-I")
                # Extract base model (e.g., "DS-2CD1043G0" from "DS-2CD1043G0-I")
                model_parts = normalized_model.split('-')
                if len(model_parts) >= 2:
                    # Try matching base model (e.g., "DS-2CD1043G0")
                    model_base = '-'.join(model_parts[:-1])
                else:
                    model_base = normalized_model
                
                # Try multiple matching strategies
                for model_key in all_firmwares.keys():
                    normalized_key = normalize_model(model_key)
                    # Exact match
                    if normalized_key == normalized_model:
                        matching_firmwares.extend(all_firmwares[model_key])
                        break
                    # Base model match
                    elif normalized_key.startswith(model_base) or model_base in normalized_key:
                        matching_firmwares.extend(all_firmwares[model_key])
                        break
                    # Reverse: check if our model starts with the key's base
                    elif normalized_model.startswith(normalized_key.split('-')[0]):
                        matching_firmwares.extend(all_firmwares[model_key])
                        break
            
            if not matching_firmwares:
                _LOGGER.debug(
                    "No matching firmware found for model %s (normalized: %s). Available models: %s",
                    self.device_model,
                    normalized_model,
                    list(all_firmwares.keys())[:10]  # Log first 10 models for debugging
                )
                return {
                    "available": False,
                    "latest_version": None,
                    "release_date": None,
                    "download_url": None,
                    "release_notes": None,
                }
            
            # Filter out invalid firmware entries and sort by version (newest first)
            valid_firmwares = []
            for fw in matching_firmwares:
                if isinstance(fw, dict) and fw.get("version") and fw.get("download_url"):
                    valid_firmwares.append(fw)
            
            if not valid_firmwares:
                _LOGGER.debug("No valid firmware entries found for model %s", normalized_model)
                return {
                    "available": False,
                    "latest_version": None,
                    "release_date": None,
                    "download_url": None,
                    "release_notes": None,
                }
            
            def get_version_key(fw: dict) -> tuple:
                version = fw.get("version", "0.0.0")
                return parse_version(version)
            
            valid_firmwares.sort(key=get_version_key, reverse=True)
            matching_firmwares = valid_firmwares
            
            # Find latest version that's newer than current
            latest_firmware = None
            for fw in matching_firmwares:
                fw_version = fw.get("version", "")
                if compare_versions(self.current_firmware, fw_version):
                    latest_firmware = fw
                    break
            
            if latest_firmware:
                # Release notes is a link to PDF (from Hikvision)
                # Check notes first, then changes, then applied_to as fallback
                notes = latest_firmware.get("notes", "").strip()
                changes = latest_firmware.get("changes", "").strip()
                applied_to = latest_firmware.get("applied_to", "").strip()
                # Only use if it looks like a URL (starts with http)
                release_notes = None
                if notes and notes.startswith("http"):
                    release_notes = notes
                elif changes and changes.startswith("http"):
                    release_notes = changes
                elif applied_to and applied_to.startswith("http"):
                    release_notes = applied_to
                
                return {
                    "available": True,
                    "latest_version": latest_firmware.get("version"),
                    "release_date": latest_firmware.get("date"),
                    "download_url": latest_firmware.get("download_url"),
                    "release_notes": release_notes,  # This will be a PDF URL
                }
            else:
                # Check if we're already on the latest
                latest = matching_firmwares[0]
                latest_version = latest.get("version", "")
                if latest_version == self.current_firmware or not compare_versions(self.current_firmware, latest_version):
                    # Release notes is a link to PDF (from Hikvision)
                    notes = latest.get("notes", "").strip()
                    changes = latest.get("changes", "").strip()
                    applied_to = latest.get("applied_to", "").strip()
                    # Only use if it looks like a URL (starts with http)
                    release_notes = None
                    if notes and notes.startswith("http"):
                        release_notes = notes
                    elif changes and changes.startswith("http"):
                        release_notes = changes
                    elif applied_to and applied_to.startswith("http"):
                        release_notes = applied_to
                    
                    return {
                        "available": False,
                        "latest_version": latest_version,
                        "release_date": latest.get("date"),
                        "download_url": latest.get("download_url"),
                        "release_notes": release_notes,  # This will be a PDF URL
                    }
            
            return {
                "available": False,
                "latest_version": None,
                "release_date": None,
                "download_url": None,
                "release_notes": None,
            }
            
        except aiohttp.ClientError as err:
            _LOGGER.warning("Error fetching firmware data from archive: %s", err)
            raise UpdateFailed(f"Error fetching firmware data: {err}") from err
        except aiohttp.ContentTypeError as err:
            _LOGGER.error("Invalid response format from firmware archive: %s", err)
            raise UpdateFailed(f"Invalid response format: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error while checking for firmware updates: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up update entity for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_info = data["device_info"]
    host = data["host"]
    device_name = device_info.get("deviceName", host)
    
    model = device_info.get("model", "")
    firmware_version = device_info.get("firmwareVersion", "")
    hardware_version = device_info.get("hardwareVersion")
    
    if not model or not firmware_version:
        _LOGGER.warning("Missing model or firmware version, skipping update entity")
        return
    
    # Create coordinator for firmware updates
    coordinator = FirmwareUpdateCoordinator(
        hass,
        model,
        firmware_version,
        hardware_version,
    )
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    entity = HikvisionFirmwareUpdate(
        coordinator,
        entry,
        host,
        device_name,
        model,
        firmware_version,
    )
    
    async_add_entities([entity])


class HikvisionFirmwareUpdate(UpdateEntity):
    """Update entity for Hikvision firmware."""
    
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_title = "Firmware Update"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        model: str,
        current_firmware: str,
    ) -> None:
        """Initialize the update entity."""
        self.coordinator = coordinator
        self._entry = entry
        self._host = host
        self._device_name = device_name
        self._model = model
        self._current_firmware = current_firmware
        
        # Get serial number for device info (matching device registry pattern)
        # Access through coordinator's hass
        self._serial_number = None
        if coordinator.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("device_info", {}).get("serialNumber"):
            self._serial_number = coordinator.hass.data[DOMAIN][entry.entry_id]["device_info"]["serialNumber"]
        
        self._attr_unique_id = f"{host}_firmware_update"
        self._attr_name = "Firmware Update"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Use serial number if available, otherwise use host (matching device registry pattern)
        if self._serial_number:
            identifiers = {(DOMAIN, self._serial_number)}
        else:
            identifiers = {(DOMAIN, self._host)}
        
        return DeviceInfo(
            identifiers=identifiers,
        )
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
    
    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version."""
        return self._current_firmware
    
    @property
    def latest_version(self) -> str | None:
        """Return the latest available version."""
        if not self.available or not self.coordinator.data:
            return None
        return self.coordinator.data.get("latest_version")
    
    @property
    def release_summary(self) -> str | None:
        """Return release summary."""
        if not self.available or not self.coordinator.data:
            return None
        return self.coordinator.data.get("release_notes")
    
    @property
    def release_url(self) -> str | None:
        """Return release URL (link to GitHub archive README for this model)."""
        if not self.available or not self.coordinator.data:
            return None
        
        # Link to GitHub archive README which has firmware info
        # The README has anchor links for each model
        model_slug = self._model.replace(" ", "-").replace("/", "-")
        return f"https://github.com/JoeyGE0/hikvision-fw-archive#{model_slug.lower()}"
    
    async def async_release_notes(self) -> str | None:
        """Return release notes (link to PDF from Hikvision)."""
        if not self.available or not self.coordinator.data:
            return None
        
        # Get release notes URL (PDF link) from coordinator data
        release_notes_url = self.coordinator.data.get("release_notes")
        
        # Build release notes text with the PDF link
        latest_version = self.coordinator.data.get("latest_version")
        release_date = self.coordinator.data.get("release_date")
        download_url = self.coordinator.data.get("download_url")
        
        lines = []
        
        if latest_version:
            lines.append(f"Latest version: {latest_version}")
        
        if release_date:
            lines.append(f"Release date: {release_date}")
        
        if self._model:
            lines.append(f"Model: {self._model}")
        
        # Add release notes PDF link if available
        if release_notes_url and release_notes_url.startswith("http"):
            lines.append("")
            lines.append("Release notes (PDF):")
            lines.append(release_notes_url)
        
        # Add download link
        if download_url:
            lines.append("")
            lines.append(f"Download firmware: {download_url}")
        
        # Add link to GitHub archive for more info
        if latest_version:
            lines.append("")
            lines.append("For more information, see:")
            lines.append(f"https://github.com/JoeyGE0/hikvision-fw-archive")
        
        return "\n".join(lines) if lines else None
    
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the update.
        
        Note: Hikvision devices do not support remote firmware installation via ISAPI.
        This method is disabled and will raise an error.
        """
        raise NotImplementedError(
            "Hikvision devices do not support remote firmware installation via ISAPI. "
            "Please download the firmware file and install it manually using Hikvision's "
            "official tools (SADP, iVMS-4200) or the device web interface."
        )
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
