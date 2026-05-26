"""Update platform for Hikvision ISAPI."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, FirmwareUpgradeError, HikvisionISAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# GitHub raw URLs for firmware archive
FIRMWARE_ARCHIVE_BASE = "https://raw.githubusercontent.com/JoeyGE0/hikvision-fw-archive/main"
FIRMWARE_INDEX_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmware_index.json"
FIRMWARES_LIVE_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_live.json"
FIRMWARES_MANUAL_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_manual.json"

# Update interval: check for firmware updates every 6 hours (archive updates twice daily)
UPDATE_INTERVAL = timedelta(hours=6)
FIRMWARE_ARCHIVE_RELEASES_URL = "https://github.com/JoeyGE0/hikvision-fw-archive/releases"
FIRMWARE_ARCHIVE_HOME_URL = "https://github.com/JoeyGE0/hikvision-fw-archive"
LICENSE_URL = "https://www.hikvision.com/en/policies/materials-license-agreement/"

HIKVISION_MODEL_PATTERN = (
    r"(DS-[0-9A-Z./()-]+|AE-[0-9A-Z./()-]+|IDS-[0-9A-Z./()-]+|HM-[0-9A-Z./()-]+|"
    r"THC-[0-9A-Z./()-]+|DVR-[0-9A-Z./()-]+|NVR-[0-9A-Z./()-]+|IPC-[0-9A-Z./()-]+|"
    r"PTZ-[0-9A-Z./()-]+|IKS-[0-9A-Z./()-]+)"
)

# ISAPI local upgrade (15.10.193 PUT/POST updateFirmware, 15.10.196 upgradeStatus)
FIRMWARE_UPLOAD_TIMEOUT = aiohttp.ClientTimeout(total=3600)
FIRMWARE_UPGRADE_POLL_TIMEOUT = 1800
FIRMWARE_REBOOT_WAIT_TIMEOUT = 300
ALLOWED_FIRMWARE_SUFFIXES = (".dav", ".digicap", ".pak", ".bin", ".zip")
MAX_FIRMWARE_BYTES = 512 * 1024 * 1024


def _normalize_hw_version(hw_version: str | None) -> str:
    """Normalize hardware version for matching."""
    if not hw_version:
        return "UNKNOWN"
    return str(hw_version).strip().upper()


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


def format_version_display(version_str: str | None) -> str | None:
    """Return version in consistent display format (Vx.y.z)."""
    if not version_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(version_str))
    if not cleaned:
        return None
    return f"V{cleaned}"


def to_github_download_url(download_url: str | None, filename: str | None) -> str | None:
    """Return a working GitHub asset URL.

    The archive stores stable /releases/download/{tag}/{file} links. Do not rewrite
    those to /releases/latest/download/ — latest only contains the most recent CI batch.
    """
    url = (download_url or "").strip()
    if url and "/releases/download/" in url and "/latest/download/" not in url:
        return url

    fname = (filename or "").strip()
    if not fname and url:
        inferred = str(download_url).split("/")[-1].split("?")[0].strip()
        if inferred and any(
            inferred.lower().endswith(ext) for ext in ALLOWED_FIRMWARE_SUFFIXES
        ):
            fname = inferred
    if fname:
        return f"{FIRMWARE_ARCHIVE_RELEASES_URL}/latest/download/{fname}"
    return url or None


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
    """Normalize model name for matching (uppercase, no parenthetical suffixes)."""
    if not model:
        return ""
    model = re.sub(r"\([^)]*\)", "", model).strip()
    return " ".join(model.split()).upper()


def _model_series_token(model: str) -> str:
    """Product family token, e.g. DS-2CD2387G3-LIS2UY/SL -> 2CD2387G3."""
    parts = model.upper().split("-")
    return parts[1] if len(parts) >= 2 else model.upper()


def _firmware_suffix_from_url(url: str) -> str:
    """Pick a safe temp-file suffix from the download URL."""
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in ALLOWED_FIRMWARE_SUFFIXES:
        return suffix
    return ".dav"


def _get_firmware_upgrade_lock(hass: HomeAssistant, entry_id: str) -> asyncio.Lock:
    """One firmware upgrade at a time per config entry."""
    locks: dict[str, asyncio.Lock] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "firmware_upgrade_locks", {}
    )
    if entry_id not in locks:
        locks[entry_id] = asyncio.Lock()
    return locks[entry_id]


def _model_match_score(device_model: str, candidate: str) -> int:
    """Score how well an archive model key matches the camera (higher is better)."""
    if not device_model or not candidate:
        return 0
    if device_model == candidate:
        return 10_000
    if device_model.startswith(candidate) or candidate.startswith(device_model):
        return 5_000 + min(len(device_model), len(candidate))
    if _model_series_token(device_model) != _model_series_token(candidate):
        return 0
    # Same series (2CD2387G3): prefer closest SKU variant
    return 1_000 + min(len(device_model), len(candidate))


def github_release_page_url(download_url: str | None) -> str | None:
    """Map /releases/download/{tag}/file.zip to the GitHub release page for that tag."""
    url = (download_url or "").strip()
    match = re.search(
        r"github\.com/JoeyGE0/hikvision-fw-archive/releases/download/([^/]+)/",
        url,
    )
    if match:
        return f"{FIRMWARE_ARCHIVE_RELEASES_URL}/tag/{match.group(1)}"
    return None


def _empty_coordinator_data() -> dict[str, Any]:
    return {
        "available": False,
        "latest_version": None,
        "release_date": None,
        "download_url": None,
        "changes_summary": None,
        "notes_pdf_url": None,
        "release_page_url": None,
        "license_url": LICENSE_URL,
        "ahead_of_archive": False,
        "filename": None,
    }


def _coordinator_data_from_firmware(
    firmware: dict[str, Any],
    *,
    available: bool,
    ahead_of_archive: bool,
) -> dict[str, Any]:
    """Build coordinator payload from one archive firmware row."""
    notes = (firmware.get("notes") or "").strip()
    changes = (firmware.get("changes") or "").strip()
    download_url = to_github_download_url(
        firmware.get("download_url"),
        firmware.get("filename"),
    )
    notes_pdf = notes if notes.startswith("http") else ""
    if not notes_pdf and changes.startswith("http"):
        notes_pdf = changes
    release_page = (
        (firmware.get("release_page_url") or "").strip()
        or github_release_page_url(firmware.get("download_url"))
        or FIRMWARE_ARCHIVE_RELEASES_URL
    )
    changes_summary = changes if changes and not changes.startswith("http") else ""
    return {
        "available": available,
        "latest_version": firmware.get("version"),
        "release_date": firmware.get("date"),
        "download_url": download_url,
        "changes_summary": changes_summary or None,
        "notes_pdf_url": notes_pdf or None,
        "release_page_url": release_page,
        "license_url": (firmware.get("license_url") or LICENSE_URL),
        "ahead_of_archive": ahead_of_archive,
        "filename": firmware.get("filename"),
    }


def _pick_index_record(
    index: dict[str, Any],
    device_model: str,
    hardware_version: str | None,
) -> dict[str, Any] | None:
    """Select best firmware_index.json row for this device."""
    models = index.get("models")
    if not isinstance(models, dict):
        return None

    normalized_model = normalize_model(device_model)
    normalized_hw = _normalize_hw_version(hardware_version)
    model_entry = models.get(normalized_model)

    if not model_entry:
        best_key: str | None = None
        best_score = 0
        for key, entry in models.items():
            score = _model_match_score(normalized_model, key)
            if score > best_score:
                best_score = score
                best_key = key
                model_entry = entry
        if best_score < 1_000:
            return None

    if not isinstance(model_entry, dict):
        return None

    by_hw = model_entry.get("by_hardware_version")
    if isinstance(by_hw, dict) and normalized_hw in by_hw:
        record = by_hw.get(normalized_hw)
        if isinstance(record, dict):
            return record

    latest = model_entry.get("latest")
    return latest if isinstance(latest, dict) else None


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
                async def _fetch_firmware_json(url: str) -> dict[str, Any]:
                    """Fetch JSON with tolerant parsing for GitHub raw content-types."""
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status != 200:
                            _LOGGER.warning("Failed to fetch firmware archive %s: HTTP %s", url, response.status)
                            return {}
                        text = await response.text()
                        if not text:
                            return {}
                        try:
                            # GitHub raw can occasionally send text/plain; parse manually.
                            import json
                            return json.loads(text)
                        except Exception as err:
                            _LOGGER.warning("Failed to parse firmware archive JSON from %s: %s", url, err)
                            return {}

                firmware_index = await _fetch_firmware_json(FIRMWARE_INDEX_URL)
                index_record = _pick_index_record(
                    firmware_index,
                    self.device_model,
                    self.hardware_version,
                )
                if index_record:
                    archive_version = (index_record.get("version") or "").strip()
                    available = bool(
                        archive_version
                        and compare_versions(self.current_firmware, archive_version)
                    )
                    ahead = bool(
                        archive_version
                        and compare_versions(archive_version, self.current_firmware)
                    )
                    return _coordinator_data_from_firmware(
                        index_record,
                        available=available,
                        ahead_of_archive=ahead and not available,
                    )

                # Fallback: scan live + manual JSON (older archive commits)
                live_firmwares = await _fetch_firmware_json(FIRMWARES_LIVE_URL)
                manual_firmwares = await _fetch_firmware_json(FIRMWARES_MANUAL_URL)

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
                    
                    norm_model = normalize_model(model)
                    if norm_model:
                        all_firmwares.setdefault(norm_model, []).append(entry)

                    for supported_model in supported_models:
                        norm_supported = normalize_model(str(supported_model))
                        if norm_supported and norm_supported != norm_model:
                            all_firmwares.setdefault(norm_supported, []).append(entry)

                    applied_to = entry.get("applied_to", "") or ""
                    for applied_model in re.findall(
                        HIKVISION_MODEL_PATTERN, applied_to, re.IGNORECASE
                    ):
                        norm_applied = normalize_model(applied_model)
                        if norm_applied:
                            all_firmwares.setdefault(norm_applied, []).append(entry)
            
            # Process live firmwares
            process_firmware_dict(live_firmwares)
            
            # Process manual firmwares
            process_firmware_dict(manual_firmwares)
            
            # Find matching firmware for this device
            normalized_model = normalize_model(self.device_model)
            normalized_hw = _normalize_hw_version(self.hardware_version)
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
                return _empty_coordinator_data()

            # Filter out invalid firmware entries and sort by version (newest first)
            valid_firmwares = []
            for fw in matching_firmwares:
                if isinstance(fw, dict) and fw.get("version") and fw.get("download_url"):
                    valid_firmwares.append(fw)
            
            if not valid_firmwares:
                _LOGGER.debug("No valid firmware entries found for model %s", normalized_model)
                return _empty_coordinator_data()

            def get_version_key(fw: dict) -> tuple:
                version = fw.get("version", "0.0.0")
                return parse_version(version)
            
            valid_firmwares.sort(key=get_version_key, reverse=True)
            # Prefer exact hardware-version matches first when available.
            exact_hw_firmwares = [
                fw for fw in valid_firmwares
                if _normalize_hw_version(fw.get("hardware_version")) == normalized_hw
            ]
            matching_firmwares = exact_hw_firmwares if exact_hw_firmwares else valid_firmwares
            
            # Find latest version that's newer than current
            latest_firmware = None
            for fw in matching_firmwares:
                fw_version = fw.get("version", "")
                if compare_versions(self.current_firmware, fw_version):
                    latest_firmware = fw
                    break
            
            if latest_firmware:
                return _coordinator_data_from_firmware(
                    latest_firmware,
                    available=True,
                    ahead_of_archive=False,
                )

            latest = matching_firmwares[0]
            latest_version = (latest.get("version") or "").strip()
            ahead = bool(
                latest_version
                and compare_versions(latest_version, self.current_firmware)
            )
            return _coordinator_data_from_firmware(
                latest,
                available=False,
                ahead_of_archive=ahead,
            )
            
        except aiohttp.ClientError as err:
            _LOGGER.warning("Error fetching firmware data from archive: %s", err)
            raise UpdateFailed(f"Error fetching firmware data: {err}") from err
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
    
    model = (device_info.get("model") or "").strip()
    firmware_version = (device_info.get("firmwareVersion") or "").strip()
    hardware_version = device_info.get("hardwareVersion")

    # Fallbacks: some devices/NVR-proxied cameras may omit root device fields.
    cameras = data.get("cameras", []) or []
    if not model and cameras:
        model = (cameras[0].get("model") or "").strip()
    if not firmware_version and cameras:
        firmware_version = (cameras[0].get("firmware") or "").strip()

    if not model:
        _LOGGER.warning("Missing model, skipping firmware update entity for %s", host)
        return
    if not firmware_version:
        # Keep entity available with unknown installed version so users still see
        # archive metadata and can diagnose mapping.
        firmware_version = "0.0.0"
    
    # Create coordinator for firmware updates
    coordinator = FirmwareUpdateCoordinator(
        hass,
        model,
        firmware_version,
        hardware_version,
    )

    # Avoid failing platform setup if archive fetch is temporarily unavailable.
    await coordinator.async_refresh()
    
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
    
    _attr_device_class = UpdateDeviceClass.FIRMWARE
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
        self._install_in_progress = False
        self._install_progress_percent: int | None = None

    @property
    def in_progress(self) -> bool:
        """Firmware install running (UpdateEntityFeature.PROGRESS)."""
        return self._install_in_progress

    @property
    def update_percentage(self) -> int | float | None:
        """Install progress 0–100 while in progress."""
        if not self._install_in_progress:
            return None
        return self._install_progress_percent

    @callback
    def _report_install_progress(self, percent: int | None) -> None:
        """Update in_progress / update_percentage for the HA UI."""
        if percent is None:
            self._install_in_progress = False
            self._install_progress_percent = None
        else:
            self._install_in_progress = True
            prior = self._install_progress_percent or 0
            self._install_progress_percent = max(prior, min(100, int(percent)))
        self.async_write_ha_state()

    async def _async_pulse_progress_until(
        self,
        start: int,
        end: int,
        stop: asyncio.Event,
        *,
        interval: float = 12.0,
        step: int = 2,
    ) -> None:
        """Creep progress forward while a blocking install step runs."""
        current = start
        while not stop.is_set() and current < end:
            await asyncio.sleep(interval)
            if stop.is_set():
                break
            current = min(end, current + step)
            self._report_install_progress(current)

    async def _async_run_blocking_with_pulse(
        self,
        func: Any,
        *args: Any,
        start: int,
        end: int,
        interval: float = 12.0,
        **kwargs: Any,
    ) -> Any:
        """Run a blocking install step in the executor while pulsing progress."""
        stop = asyncio.Event()
        pulse = asyncio.create_task(
            self._async_pulse_progress_until(start, end, stop, interval=interval)
        )
        try:
            return await self.hass.async_add_executor_job(func, *args, **kwargs)
        finally:
            stop.set()
            with contextlib.suppress(asyncio.CancelledError):
                await pulse

    async def _async_wait_for_camera_online(
        self, api: HikvisionISAPI, timeout: int = FIRMWARE_REBOOT_WAIT_TIMEOUT
    ) -> dict:
        """Poll deviceInfo after reboot; keep progress visible while camera is offline."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        progress = 96
        while loop.time() < deadline:
            self._report_install_progress(progress)
            try:
                device_info = await self.hass.async_add_executor_job(api.get_device_info)
                if device_info and (device_info.get("firmwareVersion") or "").strip():
                    return device_info
            except Exception:
                pass
            progress = min(99, progress + 1)
            await asyncio.sleep(5)
        raise HomeAssistantError(
            f"Camera {self._host} did not come back online within {timeout} seconds"
        )

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Install when a firmware package URL is available from the archive."""
        features = UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.PROGRESS
        data = self.coordinator.data or {}
        if data.get("download_url"):
            features |= UpdateEntityFeature.INSTALL
        return features

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
        """Stay available during install so progress is not hidden when the camera reboots."""
        if self._install_in_progress:
            return True
        return self.coordinator.last_update_success
    
    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version."""
        return format_version_display(self._current_firmware) or self._current_firmware
    
    @property
    def latest_version(self) -> str | None:
        """Return the latest available version."""
        if not self.available or not self.coordinator.data:
            return None
        latest = self.coordinator.data.get("latest_version")
        return format_version_display(latest) or latest
    
    @property
    def release_summary(self) -> str | None:
        """Short summary for the update card (change bullets from archive)."""
        if not self.available or not self.coordinator.data:
            return None
        summary = self.coordinator.data.get("changes_summary")
        if summary:
            return str(summary)[:255]
        if self.coordinator.data.get("ahead_of_archive"):
            return "Installed firmware is newer than the community archive."
        return None

    @property
    def release_url(self) -> str | None:
        """GitHub release page for this firmware, or archive releases index."""
        if not self.available or not self.coordinator.data:
            return None
        page = self.coordinator.data.get("release_page_url")
        if page and str(page).startswith("http"):
            return str(page)
        pdf = self.coordinator.data.get("notes_pdf_url")
        if pdf and str(pdf).startswith("http"):
            return str(pdf)
        return FIRMWARE_ARCHIVE_RELEASES_URL

    async def async_release_notes(self) -> str | None:
        """Detailed release notes for Home Assistant (matches README Notes content)."""
        if not self.available or not self.coordinator.data:
            return None

        data = self.coordinator.data
        latest_version = data.get("latest_version")
        release_date = data.get("release_date")
        download_url = data.get("download_url")
        changes_summary = data.get("changes_summary")
        notes_pdf_url = data.get("notes_pdf_url")
        release_page_url = data.get("release_page_url")
        license_url = data.get("license_url") or LICENSE_URL

        lines: list[str] = []
        firmware_filename = None
        if download_url and str(download_url).startswith("http"):
            firmware_filename = str(download_url).split("/")[-1].split("?")[0]
        package_version = None
        if firmware_filename:
            match = re.search(r"V(\d+(?:\.\d+)+)", firmware_filename, re.IGNORECASE)
            if match:
                package_version = match.group(1)

        if latest_version:
            lines.append(
                f"Latest version: {format_version_display(latest_version) or latest_version}"
            )
        if package_version and str(latest_version or "") != str(package_version):
            lines.append(f"Package version: {format_version_display(package_version) or package_version}")
        if self._current_firmware:
            lines.append(
                f"Installed version: {format_version_display(self._current_firmware) or self._current_firmware}"
            )
        if data.get("ahead_of_archive"):
            lines.append(
                "Note: Your camera firmware is newer than the highest version listed "
                "in the community archive for this model."
            )
        if release_date:
            lines.append(f"Release date: {release_date}")
        if self._model:
            lines.append(f"Model: {self._model}")

        if changes_summary:
            lines.append("")
            lines.append("Changes:")
            lines.append(str(changes_summary))

        if notes_pdf_url and str(notes_pdf_url).startswith("http"):
            lines.append("")
            lines.append("Hikvision release notes (PDF):")
            lines.append(str(notes_pdf_url))

        if download_url and str(download_url).startswith("http"):
            lines.append("")
            if firmware_filename:
                lines.append(f"Download firmware ({firmware_filename}):")
            else:
                lines.append("Download firmware:")
            lines.append(str(download_url))

        if release_page_url and str(release_page_url).startswith("http"):
            lines.append("")
            lines.append("GitHub release:")
            lines.append(str(release_page_url))

        lines.append("")
        lines.append("Hikvision Materials License Agreement:")
        lines.append(str(license_url))

        lines.append("")
        lines.append("Firmware archive:")
        lines.append(FIRMWARE_ARCHIVE_HOME_URL)

        lines.append("")
        lines.append(
            "Use **Install** in Home Assistant to upgrade this camera automatically, "
            "or open the download link above to save the firmware file for manual use. "
            "The camera will reboot during an install. Use stable power and a wired connection; "
            "do not interrupt the upgrade."
        )

        return "\n".join(lines) if lines else None

    async def _async_download_firmware(self, url: str, dest_path: str) -> None:
        """Download firmware from archive to a local temp file."""
        downloaded = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=FIRMWARE_UPLOAD_TIMEOUT) as response:
                if response.status != 200:
                    raise HomeAssistantError(
                        f"Firmware download failed: HTTP {response.status} from {url}"
                    )
                total = int(response.headers.get("Content-Length", 0) or 0)
                if total > MAX_FIRMWARE_BYTES:
                    raise HomeAssistantError("Firmware file exceeds maximum allowed size")

                with open(dest_path, "wb") as outfile:
                    async for chunk in response.content.iter_chunked(1024 * 64):
                        if not chunk:
                            continue
                        outfile.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_FIRMWARE_BYTES:
                            raise HomeAssistantError(
                                "Firmware file exceeds maximum allowed size"
                            )
                        if total > 0:
                            self._report_install_progress(
                                min(39, int(downloaded / total * 40))
                            )

        if downloaded < 1:
            raise HomeAssistantError("Downloaded firmware file is empty")

        _LOGGER.info(
            "Downloaded firmware for %s (%s bytes) to %s",
            self._host,
            downloaded,
            dest_path,
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Download firmware, upload via ISAPI, poll upgradeStatus, verify version."""
        hass = self.hass
        data = hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if not data or "api" not in data:
            raise HomeAssistantError("Integration is not ready")

        api: HikvisionISAPI = data["api"]
        coord_data = self.coordinator.data or {}
        target_version = (version or coord_data.get("latest_version") or "").strip()
        download_url = coord_data.get("download_url")

        if not download_url:
            raise HomeAssistantError("No firmware download URL available for this device")
        if not target_version:
            raise HomeAssistantError("No target firmware version specified")
        if not coord_data.get("available") and not compare_versions(
            self._current_firmware, target_version
        ):
            raise HomeAssistantError(
                f"Firmware {target_version} is not newer than installed "
                f"{self._current_firmware}"
            )

        lock = _get_firmware_upgrade_lock(hass, self._entry.entry_id)
        if lock.locked():
            raise HomeAssistantError(
                "A firmware upgrade is already in progress for this device"
            )

        suffix = _firmware_suffix_from_url(download_url)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        firmware_path = tmp.name
        tmp.close()

        loop = asyncio.get_running_loop()

        def _camera_progress(percent: int) -> None:
            mapped = min(94, 60 + int(percent * 0.34))
            loop.call_soon_threadsafe(self._report_install_progress, mapped)

        install_succeeded = False
        async with lock:
            try:
                self._report_install_progress(0)
                _LOGGER.warning(
                    "Starting firmware upgrade on %s (%s): %s -> %s",
                    self._host,
                    self._model,
                    self._current_firmware,
                    target_version,
                )

                await self._async_download_firmware(download_url, firmware_path)
                self._report_install_progress(40)

                await self._async_run_blocking_with_pulse(
                    api.upload_firmware,
                    firmware_path,
                    start=41,
                    end=58,
                    interval=10.0,
                )
                self._report_install_progress(60)

                await self._async_run_blocking_with_pulse(
                    api.wait_for_firmware_upgrade,
                    _camera_progress,
                    FIRMWARE_UPGRADE_POLL_TIMEOUT,
                    start=61,
                    end=89,
                    interval=15.0,
                )
                self._report_install_progress(90)

                device_info = await self._async_wait_for_camera_online(api)
                new_firmware = (device_info.get("firmwareVersion") or "").strip()

                if not new_firmware:
                    raise HomeAssistantError(
                        "Upgrade finished but could not read new firmware version"
                    )

                self._current_firmware = new_firmware
                self.coordinator.current_firmware = new_firmware
                data["device_info"]["firmwareVersion"] = new_firmware
                await self.coordinator.async_refresh()
                self.async_write_ha_state()

                if parse_version(new_firmware) < parse_version(target_version):
                    _LOGGER.warning(
                        "Firmware on %s after upgrade is %s (expected %s) — "
                        "verify manually in the web UI",
                        self._host,
                        new_firmware,
                        target_version,
                    )

                install_succeeded = True
                self._report_install_progress(100)
                _LOGGER.warning(
                    "Firmware upgrade completed on %s: now running %s",
                    self._host,
                    new_firmware,
                )
                await asyncio.sleep(3)

            except AuthenticationError as err:
                raise HomeAssistantError(f"Authentication failed: {err}") from err
            except FirmwareUpgradeError as err:
                hint = ""
                err_text = str(err)
                if err.sub_status in ("upgrading", "badFlash", "badLanguage"):
                    hint = (
                        " Device may be busy, flash error, or language mismatch "
                        "(ISAPI subStatusCode)."
                    )
                elif "errCode = 40" in err_text or "ret[40]" in err_text:
                    hint = (
                        " Firmware package rejected (wrong file type, model, or region). "
                        "Use the digicap.dav inside the official zip for this exact model."
                    )
                raise HomeAssistantError(f"Firmware upgrade failed: {err}.{hint}") from err
            except HomeAssistantError:
                raise
            except Exception as err:
                _LOGGER.exception("Unexpected firmware upgrade error on %s", self._host)
                raise HomeAssistantError(f"Firmware upgrade failed: {err}") from err
            finally:
                self._report_install_progress(None)
                if install_succeeded:
                    await self.coordinator.async_refresh()
                try:
                    os.unlink(firmware_path)
                except OSError:
                    pass
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
