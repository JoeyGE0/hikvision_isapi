"""Camera platform for Hikvision ISAPI."""
import logging
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up camera entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    cameras = data.get("cameras", [])
    device_info = data["device_info"]
    device_name = device_info.get("deviceName", host)
    is_nvr = data.get("capabilities", {}).get("is_nvr", False)

    entities = []
    
    # Create camera entity for each discovered camera/channel and each stream type
    for camera in cameras:
        camera_id = camera["id"]
        camera_name = camera["name"] if is_nvr or len(cameras) > 1 else device_name
        
        # Get available streams for this camera
        try:
            streams = await hass.async_add_executor_job(api.get_camera_streams, camera_id)
        except Exception as e:
            _LOGGER.error("Failed to get streams for camera %d: %s", camera_id, e)
            streams = []
        
        if not streams:
            # Fallback: create single camera entity if no streams found
            _LOGGER.warning("No streams found for camera %d, creating default camera entity", camera_id)
            entities.append(
                HikvisionCamera(coordinator, api, entry, host, camera_name, camera_id, None),
            )
        else:
            # Create entity for each stream
            for stream in streams:
                entities.append(
                    HikvisionCamera(coordinator, api, entry, host, camera_name, camera_id, stream),
                )

    async_add_entities(entities)


class HikvisionCamera(Camera):
    """Camera entity for Hikvision camera stream."""

    _attr_icon = "mdi:camera"

    def __init__(
        self, 
        coordinator: HikvisionDataUpdateCoordinator, 
        api: HikvisionISAPI, 
        entry: ConfigEntry, 
        host: str, 
        device_name: str, 
        camera_id: int = 1,
        stream: dict = None
    ):
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._camera_id = camera_id
        self._stream_info = stream  # Use _stream_info to avoid conflicts with Home Assistant's stream property
        
        # Only enable stream feature if we have a stream configured
        if stream:
            self._attr_supported_features = CameraEntityFeature.STREAM
        else:
            self._attr_supported_features = CameraEntityFeature(0)  # No features
        
        # Build unique_id
        if stream:
            # Use stream ID for unique_id (e.g., garage_101, garage_102)
            device_name_slug = slugify(device_name.lower())
            self._attr_unique_id = f"{host}_{stream['id']}"
            
            # Main stream (type_id=1) uses device name + "Main", others are disabled by default
            if stream["type_id"] == 1:
                self._attr_name = f"{device_name} Main"
                self._attr_entity_registry_enabled_default = True
            else:
                # Other streams: add stream type suffix and disable by default
                self._attr_name = f"{device_name} {stream['type']}"
                self._attr_entity_registry_enabled_default = False
        else:
            # Fallback: old snapshot-style entity
            if camera_id == 1 and len(api.cameras) == 1:
                self._attr_name = f"{device_name} Snapshot"
                self._attr_unique_id = f"{host}_camera"
            else:
                self._attr_name = f"{device_name} Snapshot"
                self._attr_unique_id = f"{host}_camera_{camera_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Get device data to check if this is an NVR camera
        data = self.coordinator.hass.data[DOMAIN][self._entry.entry_id]
        device_info = data["device_info"]
        cameras = data.get("cameras", [])
        capabilities = data.get("capabilities", {})
        is_nvr = capabilities.get("is_nvr", False)
        nvr_device_identifier = data.get("nvr_device_identifier", self._host)
        
        # Find camera info to get serial number
        camera_info = None
        for cam in cameras:
            if cam.get("id") == self._camera_id:
                camera_info = cam
                break
        
        # Use camera serial if available (NVR), otherwise device serial/host
        if camera_info and camera_info.get("serial_no"):
            device_identifier = camera_info["serial_no"]
        else:
            device_identifier = device_info.get("serialNumber") or self._host
        
        # Strip all stream type suffixes from device name (Main, Snapshot, Transcoded Stream, Sub-stream, etc.)
        device_name_clean = self._attr_name.replace(" Main", "").replace(" Snapshot", "")
        # Also strip common stream type suffixes
        for suffix in [" Transcoded Stream", " Transcoded", " Sub-stream", " Sub", " Third Stream", " Third"]:
            device_name_clean = device_name_clean.replace(suffix, "")
        
        device_info_dict = {
            "identifiers": {(DOMAIN, device_identifier)},
            "manufacturer": device_info.get("manufacturer", "Hikvision").title(),
            "model": camera_info.get("model") if camera_info else device_info.get("model", "Hikvision Camera"),
            "name": device_name_clean,
            "sw_version": camera_info.get("firmware") if camera_info else device_info.get("firmwareVersion"),
        }
        
        # Add via_device for NVR cameras (camera_id > 0 on NVR)
        if is_nvr and self._camera_id > 0 and nvr_device_identifier:
            device_info_dict["via_device"] = (DOMAIN, nvr_device_identifier)
        
        return DeviceInfo(**device_info_dict)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if self._stream_info:
            # Get camera IP for proxied cameras
            data = self.coordinator.hass.data[DOMAIN][self._entry.entry_id]
            cameras = data.get("cameras", [])
            camera_info = None
            for cam in cameras:
                if cam.get("id") == self._camera_id:
                    camera_info = cam
                    break
            camera_ip = camera_info.get("ip_addr") if camera_info else None
            
            return await self.hass.async_add_executor_job(
                self.api.get_stream_source, self._stream_info["id"], camera_ip
            )
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            # Check if this camera is proxied (NVR camera)
            data = self.coordinator.hass.data[DOMAIN][self._entry.entry_id]
            cameras = data.get("cameras", [])
            camera_info = None
            for cam in cameras:
                if cam.get("id") == self._camera_id:
                    camera_info = cam
                    break
            use_proxy_url = camera_info and camera_info.get("connection_type") == "proxied"
            
            if self._stream_info:
                # Use stream-specific snapshot
                image = await self.hass.async_add_executor_job(
                    self.api.get_snapshot, self._camera_id, self._stream_info["id"], use_proxy_url
                )
            else:
                # Fallback to old method
                image = await self.hass.async_add_executor_job(
                    self.api.get_snapshot, self._camera_id, None, use_proxy_url
                )
            return image
        except Exception as e:
            _LOGGER.error("Failed to get camera snapshot for camera %d: %s", self._camera_id, e)
            return None

