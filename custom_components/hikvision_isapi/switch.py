"""Switch platform for Hikvision ISAPI."""
from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .api import HikvisionISAPI
from .coordinator import HikvisionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up switch entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)

    entities = [
        HikvisionAlarmInputSwitch(coordinator, api, entry, host, device_name, 1),
        HikvisionAlarmOutputSwitch(coordinator, api, entry, host, device_name, 1),
        HikvisionIntrusionDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionLineCrossingDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionMotionDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionRegionEntranceDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionRegionExitingDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionSceneChangeDetectionSwitch(coordinator, api, entry, host, device_name),
        HikvisionVideoTamperingDetectionSwitch(coordinator, api, entry, host, device_name),
    ]

    async_add_entities(entities)


class HikvisionDetectionSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Hikvision detection switches."""

    def __init__(
        self,
        coordinator: HikvisionDataUpdateCoordinator,
        api: HikvisionISAPI,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        data_key: str,
        unique_id_suffix: str,
        name_suffix: str,
        icon: str,
    ):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._data_key = data_key
        self._attr_unique_id = f"{host}_{unique_id_suffix}"
        self._attr_name = f"{device_name} {name_suffix}"
        self._attr_icon = icon

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
    def is_on(self) -> bool:
        """Return if detection is enabled."""
        if self.coordinator.data and self._data_key in self.coordinator.data:
            return self.coordinator.data[self._data_key].get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn on the detection."""
        await self.hass.async_add_executor_job(self._turn_on_sync)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the detection."""
        await self.hass.async_add_executor_job(self._turn_off_sync)
        await self.coordinator.async_request_refresh()

    def _turn_on_sync(self):
        """Turn on synchronously."""
        raise NotImplementedError

    def _turn_off_sync(self):
        """Turn off synchronously."""
        raise NotImplementedError


class HikvisionAlarmInputSwitch(HikvisionDetectionSwitch):
    """Switch for alarm input."""

    def __init__(self, coordinator, api, entry, host, device_name, input_id):
        """Initialize the alarm input switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "alarm_input",
            f"alarm_input_{input_id}",
            f"Alarm Input {input_id}",
            "mdi:alarm-light",
        )
        self._input_id = input_id

    def _turn_on_sync(self):
        """Turn on alarm input."""
        self.api.set_alarm_input(self._input_id, True)

    def _turn_off_sync(self):
        """Turn off alarm input."""
        self.api.set_alarm_input(self._input_id, False)


class HikvisionAlarmOutputSwitch(HikvisionDetectionSwitch):
    """Switch for alarm output."""

    def __init__(self, coordinator, api, entry, host, device_name, output_id):
        """Initialize the alarm output switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "alarm_output",
            f"alarm_output_{output_id}",
            f"Alarm Output {output_id}",
            "mdi:alarm-light-outline",
        )
        self._output_id = output_id

    def _turn_on_sync(self):
        """Turn on alarm output."""
        self.api.set_alarm_output(self._output_id, True)

    def _turn_off_sync(self):
        """Turn off alarm output."""
        self.api.set_alarm_output(self._output_id, False)


class HikvisionIntrusionDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for intrusion detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the intrusion detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "intrusion",
            "intrusion_detection",
            "Intrusion Detection",
            "mdi:shield-alert",
        )

    def _turn_on_sync(self):
        """Turn on intrusion detection."""
        self.api.set_intrusion_detection(True)

    def _turn_off_sync(self):
        """Turn off intrusion detection."""
        self.api.set_intrusion_detection(False)


class HikvisionLineCrossingDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for line crossing detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the line crossing detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "line_crossing",
            "line_crossing_detection",
            "Line Crossing Detection",
            "mdi:vector-line",
        )

    def _turn_on_sync(self):
        """Turn on line crossing detection."""
        self.api.set_line_crossing_detection(True)

    def _turn_off_sync(self):
        """Turn off line crossing detection."""
        self.api.set_line_crossing_detection(False)


class HikvisionMotionDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for motion detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the motion detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "motion",
            "motion_detection",
            "Motion Detection",
            "mdi:motion-sensor",
        )

    def _turn_on_sync(self):
        """Turn on motion detection."""
        self.api.set_motion_detection(True)

    def _turn_off_sync(self):
        """Turn off motion detection."""
        self.api.set_motion_detection(False)


class HikvisionRegionEntranceDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for region entrance detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the region entrance detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "region_entrance",
            "region_entrance_detection",
            "Region Entrance Detection",
            "mdi:arrow-down-bold",
        )

    def _turn_on_sync(self):
        """Turn on region entrance detection."""
        self.api.set_region_entrance_detection(True)

    def _turn_off_sync(self):
        """Turn off region entrance detection."""
        self.api.set_region_entrance_detection(False)


class HikvisionRegionExitingDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for region exiting detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the region exiting detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "region_exiting",
            "region_exiting_detection",
            "Region Exiting Detection",
            "mdi:arrow-up-bold",
        )

    def _turn_on_sync(self):
        """Turn on region exiting detection."""
        self.api.set_region_exiting_detection(True)

    def _turn_off_sync(self):
        """Turn off region exiting detection."""
        self.api.set_region_exiting_detection(False)


class HikvisionSceneChangeDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for scene change detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the scene change detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "scene_change",
            "scene_change_detection",
            "Scene Change Detection",
            "mdi:image-edit",
        )

    def _turn_on_sync(self):
        """Turn on scene change detection."""
        self.api.set_scene_change_detection(True)

    def _turn_off_sync(self):
        """Turn off scene change detection."""
        self.api.set_scene_change_detection(False)


class HikvisionVideoTamperingDetectionSwitch(HikvisionDetectionSwitch):
    """Switch for video tampering detection."""

    def __init__(self, coordinator, api, entry, host, device_name):
        """Initialize the video tampering detection switch."""
        super().__init__(
            coordinator,
            api,
            entry,
            host,
            device_name,
            "tamper",
            "video_tampering_detection",
            "Video Tampering Detection",
            "mdi:shield-alert",
        )

    def _turn_on_sync(self):
        """Turn on video tampering detection."""
        self.api.set_tamper_detection(True)

    def _turn_off_sync(self):
        """Turn off video tampering detection."""
        self.api.set_tamper_detection(False)
