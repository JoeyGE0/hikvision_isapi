"""Update platform for Hikvision ISAPI."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, FirmwareUpgradeError, HikvisionISAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# GitHub raw URLs for firmware archive
FIRMWARE_ARCHIVE_BASE = "https://raw.githubusercontent.com/JoeyGE0/hikvision-fw-archive/main"
FIRMWARES_LIVE_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_live.json"
FIRMWARES_MANUAL_URL = f"{FIRMWARE_ARCHIVE_BASE}/firmwares_manual.json"

# Update interval: check for firmware updates every 6 hours (archive updates twice daily)
UPDATE_INTERVAL = timedelta(hours=6)
FIRMWARE_ARCHIVE_RELEASES_URL = "https://github.com/JoeyGE0/hikvision-fw-archive/releases"

# ISAPI local upgrade (15.10.193 / 15.10.196)
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
    """Parse version string into tuple for comparison."""
    if not version_str:
        return (0,)

    version_str = re.sub(r"[^\d.]", "", str(version_str))

    try:
        parts = [int(x) for x in version_str.split(".") if x]
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
    """Prefer GitHub release-style download URL for consistency/reliability."""
    fname = (filename or "").strip()
    if not fname and download_url:
        inferred = str(download_url).split("/")[-1].split("?")[0].strip()
        if inferred and any(
            inferred.lower().endswith(ext) for ext in ALLOWED_FIRMWARE_SUFFIXES
        ):
            fname = inferred
    if fname:
        return f"{FIRMWARE_ARCHIVE_RELEASES_URL}/latest/download/{fname}"
    return download_url


def compare_versions(current: str, available: str) -> bool:
    """Compare version strings. Returns True if available is newer than current."""
    current_tuple = parse_version(current)
    available_tuple = parse_version(available)

    max_len = max(len(current_tuple), len(available_tuple))
    current_padded = current_tuple + (0,) * (max_len - len(current_tuple))
    available_padded = available_tuple + (0,) * (max_len - len(available_tuple))

    return available_padded > current_padded


def normalize_model(model: str) -> str:
    """Normalize model name for matching."""
    if not model:
        return ""

    model = re.sub(r"\([^)]*\)", "", model).strip()
    return model.strip()


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
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status != 200:
                            _LOGGER.warning(
                                "Failed to fetch firmware archive %s: HTTP %s",
                                url,
                                response.status,
                            )
                            return {}
                        text = await response.text()
                        if not text:
                            return {}
                        try:
                            import json

                            return json.loads(text)
                        except Exception as err:
                            _LOGGER.warning(
                                "Failed to parse firmware archive JSON from %s: %s",
                                url,
                                err,
                            )
                            return {}

                live_firmwares = await _fetch_firmware_json(FIRMWARES_LIVE_URL)
                manual_firmwares = await _fetch_firmware_json(FIRMWARES_MANUAL_URL)

            all_firmwares: dict[str, list] = {}

            def process_firmware_dict(firmware_dict: dict) -> None:
                if not isinstance(firmware_dict, dict):
                    return

                for _key, entry in firmware_dict.items():
                    if not isinstance(entry, dict):
                        continue

                    model = entry.get("model", "")
                    if not model:
                        continue

                    supported_models = entry.get("supported_models", [])
                    if not isinstance(supported_models, list):
                        supported_models = []

                    if model not in all_firmwares:
                        all_firmwares[model] = []
                    all_firmwares[model].append(entry)

                    for supported_model in supported_models:
                        if supported_model and supported_model != model:
                            if supported_model not in all_firmwares:
                                all_firmwares[supported_model] = []
                            all_firmwares[supported_model].append(entry)

            process_firmware_dict(live_firmwares)
            process_firmware_dict(manual_firmwares)

            normalized_model = normalize_model(self.device_model)
            normalized_hw = _normalize_hw_version(self.hardware_version)
            matching_firmwares: list = []

            if normalized_model in all_firmwares:
                matching_firmwares = all_firmwares[normalized_model]
            else:
                model_parts = normalized_model.split("-")
                model_base = (
                    "-".join(model_parts[:-1]) if len(model_parts) >= 2 else normalized_model
                )

                for model_key in all_firmwares:
                    normalized_key = normalize_model(model_key)
                    if normalized_key == normalized_model:
                        matching_firmwares.extend(all_firmwares[model_key])
                        break
                    if normalized_key.startswith(model_base) or model_base in normalized_key:
                        matching_firmwares.extend(all_firmwares[model_key])
                        break
                    if normalized_model.startswith(normalized_key.split("-")[0]):
                        matching_firmwares.extend(all_firmwares[model_key])
                        break

            if not matching_firmwares:
                return {
                    "available": False,
                    "latest_version": None,
                    "release_date": None,
                    "download_url": None,
                    "release_notes": None,
                    "filename": None,
                }

            valid_firmwares = [
                fw
                for fw in matching_firmwares
                if isinstance(fw, dict) and fw.get("version") and fw.get("download_url")
            ]

            if not valid_firmwares:
                return {
                    "available": False,
                    "latest_version": None,
                    "release_date": None,
                    "download_url": None,
                    "release_notes": None,
                    "filename": None,
                }

            valid_firmwares.sort(key=lambda fw: parse_version(fw.get("version", "0.0.0")), reverse=True)
            exact_hw_firmwares = [
                fw
                for fw in valid_firmwares
                if _normalize_hw_version(fw.get("hardware_version")) == normalized_hw
            ]
            matching_firmwares = exact_hw_firmwares if exact_hw_firmwares else valid_firmwares

            latest_firmware = None
            for fw in matching_firmwares:
                fw_version = fw.get("version", "")
                if compare_versions(self.current_firmware, fw_version):
                    latest_firmware = fw
                    break

            def _release_notes_url(fw: dict) -> str | None:
                for field in ("notes", "changes", "applied_to"):
                    value = (fw.get(field) or "").strip()
                    if value.startswith("http"):
                        return value
                return None

            if latest_firmware:
                return {
                    "available": True,
                    "latest_version": latest_firmware.get("version"),
                    "release_date": latest_firmware.get("date"),
                    "download_url": to_github_download_url(
                        latest_firmware.get("download_url"),
                        latest_firmware.get("filename"),
                    ),
                    "release_notes": _release_notes_url(latest_firmware),
                    "filename": latest_firmware.get("filename"),
                }

            latest = matching_firmwares[0]
            latest_version = latest.get("version", "")
            if latest_version == self.current_firmware or not compare_versions(
                self.current_firmware, latest_version
            ):
                return {
                    "available": False,
                    "latest_version": latest_version,
                    "release_date": latest.get("date"),
                    "download_url": to_github_download_url(
                        latest.get("download_url"),
                        latest.get("filename"),
                    ),
                    "release_notes": _release_notes_url(latest),
                    "filename": latest.get("filename"),
                }

            return {
                "available": False,
                "latest_version": None,
                "release_date": None,
                "download_url": None,
                "release_notes": None,
                "filename": None,
            }

        except aiohttp.ClientError as err:
            _LOGGER.warning("Error fetching firmware data from archive: %s", err)
            raise UpdateFailed(f"Error fetching firmware data: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error while checking for firmware updates: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entity for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_info = data["device_info"]
    host = data["host"]
    device_name = device_info.get("deviceName", host)

    model = (device_info.get("model") or "").strip()
    firmware_version = (device_info.get("firmwareVersion") or "").strip()
    hardware_version = device_info.get("hardwareVersion")

    cameras = data.get("cameras", []) or []
    if not model and cameras:
        model = (cameras[0].get("model") or "").strip()
    if not firmware_version and cameras:
        firmware_version = (cameras[0].get("firmware") or "").strip()

    if not model:
        _LOGGER.warning("Missing model, skipping firmware update entity for %s", host)
        return
    if not firmware_version:
        firmware_version = "0.0.0"

    coordinator = FirmwareUpdateCoordinator(
        hass,
        model,
        firmware_version,
        hardware_version,
    )

    await coordinator.async_refresh()

    async_add_entities(
        [
            HikvisionFirmwareUpdate(
                coordinator,
                entry,
                host,
                device_name,
                model,
                firmware_version,
            )
        ]
    )


class HikvisionFirmwareUpdate(UpdateEntity):
    """Update entity for Hikvision firmware."""

    _attr_supported_features = (
        UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.PROGRESS
    )
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

        self._serial_number = None
        entry_data = coordinator.hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        if entry_data.get("device_info", {}).get("serialNumber"):
            self._serial_number = entry_data["device_info"]["serialNumber"]

        self._attr_unique_id = f"{host}_firmware_update"
        self._attr_name = "Firmware Update"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        if self._serial_number:
            identifiers = {(DOMAIN, self._serial_number)}
        else:
            identifiers = {(DOMAIN, self._host)}

        return DeviceInfo(identifiers=identifiers)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
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
        """Return release summary."""
        if not self.available or not self.coordinator.data:
            return None
        return self.coordinator.data.get("release_notes")

    @property
    def release_url(self) -> str | None:
        """Return announcement URL."""
        if not self.available or not self.coordinator.data:
            return None
        release_notes = self.coordinator.data.get("release_notes")
        if release_notes and str(release_notes).startswith("http"):
            return release_notes
        return FIRMWARE_ARCHIVE_RELEASES_URL

    async def async_release_notes(self) -> str | None:
        """Return release notes."""
        if not self.available or not self.coordinator.data:
            return None

        release_notes_url = self.coordinator.data.get("release_notes")
        latest_version = self.coordinator.data.get("latest_version")
        release_date = self.coordinator.data.get("release_date")
        download_url = self.coordinator.data.get("download_url")

        lines = []
        if latest_version:
            lines.append(
                f"Latest version: {format_version_display(latest_version) or latest_version}"
            )
        if release_date:
            lines.append(f"Release date: {release_date}")
        if self._model:
            lines.append(f"Model: {self._model}")
        if release_notes_url and release_notes_url.startswith("http"):
            lines.extend(["", "Release notes (PDF):", release_notes_url])
        if download_url:
            lines.extend(["", f"Download firmware: {download_url}"])
        lines.extend(
            [
                "",
                "Install via Home Assistant uploads firmware using ISAPI",
                "PUT /ISAPI/System/updateFirmware, then polls upgradeStatus.",
                "",
                "Warning: interrupted upgrades can brick the device. Use stable power and LAN.",
            ]
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
                            await self.async_update_progress(
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
        upgrade_progress: list[int] = [0]

        def _camera_progress(percent: int) -> None:
            upgrade_progress[0] = percent
            mapped = 60 + int(percent * 0.35)
            loop.call_soon_threadsafe(
                lambda p=mapped: hass.async_create_task(self.async_update_progress(p))
            )

        async with lock:
            try:
                await self.async_update_progress(0)
                _LOGGER.warning(
                    "Starting firmware upgrade on %s (%s): %s -> %s",
                    self._host,
                    self._model,
                    self._current_firmware,
                    target_version,
                )

                await self._async_download_firmware(download_url, firmware_path)
                await self.async_update_progress(40)

                await hass.async_add_executor_job(api.upload_firmware, firmware_path)
                await self.async_update_progress(60)

                await hass.async_add_executor_job(
                    api.wait_for_firmware_upgrade,
                    _camera_progress,
                    FIRMWARE_UPGRADE_POLL_TIMEOUT,
                )
                await self.async_update_progress(95)

                device_info = await hass.async_add_executor_job(
                    api.wait_for_device_online,
                    FIRMWARE_REBOOT_WAIT_TIMEOUT,
                )
                new_firmware = (device_info.get("firmwareVersion") or "").strip()

                await self.async_update_progress(100)

                if not new_firmware:
                    raise HomeAssistantError(
                        "Upgrade finished but could not read new firmware version"
                    )

                self._current_firmware = new_firmware
                self.coordinator.current_firmware = new_firmware
                data["device_info"]["firmwareVersion"] = new_firmware
                await self.coordinator.async_refresh()

                if parse_version(new_firmware) < parse_version(target_version):
                    _LOGGER.warning(
                        "Firmware on %s after upgrade is %s (expected %s) — "
                        "verify manually in the device web UI",
                        self._host,
                        new_firmware,
                        target_version,
                    )

                _LOGGER.warning(
                    "Firmware upgrade completed on %s: now running %s",
                    self._host,
                    new_firmware,
                )

            except AuthenticationError as err:
                raise HomeAssistantError(f"Authentication failed: {err}") from err
            except FirmwareUpgradeError as err:
                hint = ""
                if err.sub_status in ("upgrading", "badFlash", "badLanguage"):
                    hint = (
                        " Device may be busy, flash error, or language mismatch "
                        "(ISAPI subStatusCode)."
                    )
                raise HomeAssistantError(f"Firmware upgrade failed: {err}.{hint}") from err
            except HomeAssistantError:
                raise
            except Exception as err:
                _LOGGER.exception("Unexpected firmware upgrade error on %s", self._host)
                raise HomeAssistantError(f"Firmware upgrade failed: {err}") from err
            finally:
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
