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
        streams = await hass.async_add_executor_job(api.get_camera_streams, camera_id)
        
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
    _attr_supported_features = CameraEntityFeature.STREAM

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
        self.stream = stream
        
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if self.stream:
            return await self.hass.async_add_executor_job(
                self.api.get_stream_source, self.stream["id"]
            )
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            if self.stream:
                # Use stream-specific snapshot
                image = await self.hass.async_add_executor_job(
                    self.api.get_snapshot, self._camera_id, self.stream["id"]
                )
            else:
                # Fallback to old method
                image = await self.hass.async_add_executor_job(
                    self.api.get_snapshot, self._camera_id
                )
            return image
        except Exception as e:
            _LOGGER.error("Failed to get camera snapshot for camera %d: %s", self._camera_id, e)
            return None

