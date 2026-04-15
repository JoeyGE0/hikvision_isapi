"""Select platform for Hikvision ISAPI."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .device_helpers import get_primary_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up select entities for the entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    host = data["host"]
    device_name = data["device_info"].get("deviceName", host)
    detected_features = data.get("detected_features", {})

    entities = []
    
    # Only add entities if their features are detected
    if detected_features.get("supplement_light_mode", False):
        entities.append(HikvisionLightModeSelect(coordinator, api, entry, host, device_name))
    if detected_features.get("day_night_mode", False):
        entities.append(HikvisionBrightnessControlSelect(coordinator, api, entry, host, device_name))
        entities.append(HikvisionIRModeSelect(coordinator, api, entry, host, device_name))
    if detected_features.get("motion_detection", False):
        entities.append(HikvisionMotionTargetTypeSelect(coordinator, api, entry, host, device_name))
    if detected_features.get("audio_alarm_type", False):
        entities.append(HikvisionAudioTypeSelect(coordinator, api, entry, host, device_name))
    if detected_features.get("audio_alarm_sound", False):
        entities.append(HikvisionWarningSoundSelect(coordinator, api, entry, host, device_name))

    async_add_entities(entities)


class HikvisionLightModeSelect(SelectEntity):
    """Select entity for supplement light mode."""

    _attr_unique_id = "hikvision_light_mode"
    _attr_options = ["Smart", "White Supplement Light", "IR Supplement Light", "Off"]
    _attr_icon = "mdi:lightbulb"

    # Map display names to API values
    _api_value_map = {
        "Smart": "eventIntelligence",
        "White Supplement Light": "colorVuWhiteLight",
        "IR Supplement Light": "irLight",
        "Off": "close",
    }
    # Reverse map for reading
    _display_value_map = {v: k for k, v in _api_value_map.items()}

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Supplement Light"
        self._attr_unique_id = f"{host}_light_mode"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value

        # Otherwise use coordinator data - convert API value to display name
        if not self.available:
            return None
        if self.coordinator.data and "supplement_light" in self.coordinator.data:
            api_value = self.coordinator.data["supplement_light"].get("mode")
            display_value = self._display_value_map.get(api_value)
            if display_value in self._attr_options:
                return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        # Convert display name to API value
        api_value = self._api_value_map.get(option, option)

        # Optimistic update - show immediately
        self._optimistic_value = option
        self.async_write_ha_state()

        # Send to device (using API value)
        success = await self.hass.async_add_executor_job(
            self.api.set_supplement_light, api_value
        )

        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (
                self.coordinator.data
                and self.coordinator.data.get("supplement_light", {}).get("mode") == api_value
            ):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionBrightnessControlSelect(SelectEntity):
    """Select entity for light brightness control mode."""

    _attr_unique_id = "hikvision_brightness_control_mode"
    _attr_options = ["Auto", "Manual"]
    _attr_icon = "mdi:brightness-auto"
    _attr_entity_registry_enabled_default = False

    _api_value_map = {
        "Auto": "auto",
        "Manual": "manual",
    }
    _display_value_map = {v: k for k, v in _api_value_map.items()}

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Light Brightness Control"
        self._attr_unique_id = f"{host}_brightness_control_mode"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value

        # Otherwise use coordinator data - convert API value to display name
        if not self.available:
            return None
        if self.coordinator.data and "supplement_light" in self.coordinator.data:
            data = self.coordinator.data["supplement_light"]
            api_value = data.get("brightnessRegulatMode") or data.get(
                "mixedLightBrightnessRegulatMode"
            )
            display_value = self._display_value_map.get(api_value)
            if display_value in self._attr_options:
                return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        api_value = self._api_value_map.get(option, option)

        self._optimistic_value = option
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_brightness_control_mode, api_value
        )

        if success:
            await self.coordinator.async_request_refresh()
            if self.coordinator.data and "supplement_light" in self.coordinator.data:
                data = self.coordinator.data["supplement_light"]
                api_value_now = data.get("brightnessRegulatMode") or data.get(
                    "mixedLightBrightnessRegulatMode"
                )
                if api_value_now == api_value:
                    self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionIRModeSelect(SelectEntity):
    """Select entity for IR cut mode."""

    _attr_unique_id = "hikvision_ir_mode"
    _attr_options = ["Day", "Night", "Auto"]
    _attr_icon = "mdi:weather-night"
    
    # Map display names to API values
    _api_value_map = {
        "Day": "day",
        "Night": "night",
        "Auto": "auto"
    }
    # Reverse map for reading
    _display_value_map = {v: k for k, v in _api_value_map.items()}

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Day/Night Switch"
        self._attr_unique_id = f"{host}_ir_mode"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data - convert API value to display name
        if not self.available:
            return None
        if self.coordinator.data and "ircut" in self.coordinator.data:
            api_value = self.coordinator.data["ircut"].get("mode")
            display_value = self._display_value_map.get(api_value)
            if display_value in self._attr_options:
                return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        # Convert display name to API value
        api_value = self._api_value_map.get(option, option)
        
        # Optimistic update - show immediately
        self._optimistic_value = option
        self.async_write_ha_state()
        
        # Send to device (using API value)
        success = await self.hass.async_add_executor_job(
            self.api.set_ircut_mode, api_value
        )
        
        if success:
            # Refresh coordinator to sync with device
            await self.coordinator.async_request_refresh()
            # Only clear optimistic if coordinator confirms the change
            if (self.coordinator.data and 
                self.coordinator.data.get("ircut", {}).get("mode") == api_value):
                self._optimistic_value = None
        else:
            # Write failed, clear optimistic and let coordinator show actual state
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionMotionTargetTypeSelect(SelectEntity):
    """Select entity for motion detection target type."""

    _attr_unique_id = "hikvision_motion_target_type"
    _attr_options = ["human", "vehicle", "human,vehicle"]
    _attr_icon = "mdi:target"

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Motion Target Type"
        self._attr_unique_id = f"{host}_motion_target_type"
        self._optimistic_value = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Use optimistic value if set (immediate feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value
        
        # Otherwise use coordinator data - convert API value to display name
        if not self.available:
            return None
        if self.coordinator.data and "motion" in self.coordinator.data:
            target_type = self.coordinator.data["motion"].get("targetType")
            if target_type and target_type in self._attr_options:
                return target_type
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        self._optimistic_value = option
        self.async_write_ha_state()
        
        success = await self.hass.async_add_executor_job(
            self.api.set_motion_target_type, option
        )
        
        if success:
            await self.coordinator.async_request_refresh()
            if (self.coordinator.data and 
                self.coordinator.data.get("motion", {}).get("targetType") == option):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class HikvisionAudioTypeSelect(SelectEntity):
    """Select entity for audio alarm type (options from device capabilities when available)."""

    _attr_unique_id = "hikvision_audio_type"
    _attr_icon = "mdi:waveform"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Audio Type"
        self._attr_unique_id = f"{host}_audio_type"
        self._optimistic_value = None
        self._label_to_api: dict[str, str] = {}
        self._api_to_label: dict[str, str] = {}
        self._attr_options: list[str] = []
        self._sync_audio_class_options()

    def _sync_audio_class_options(self) -> None:
        """Rebuild labels from coordinator capability snapshot."""
        norm = (self.coordinator.data or {}).get("audio_alarm_capabilities") or {}
        rows: list[dict] = [
            dict(r) for r in (norm.get("audio_classes") or []) if isinstance(r, dict)
        ]
        known_api = {str(r.get("value")) for r in rows if r.get("value")}
        audio_alarm = (self.coordinator.data or {}).get("audio_alarm") or {}
        cur_cls = audio_alarm.get("audioClass")
        if isinstance(cur_cls, str) and cur_cls and cur_cls not in known_api:
            pretty = {
                "alertAudio": "Alert Audio",
                "promptAudio": "Prompt Audio",
                "customAudio": "Custom Audio",
            }.get(cur_cls, cur_cls)
            rows.append({"value": cur_cls, "label": pretty})

        self._label_to_api.clear()
        self._api_to_label.clear()
        labels: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            val = row.get("value")
            lbl = row.get("label")
            if not val or not lbl:
                continue
            labels.append(str(lbl))
            self._label_to_api[str(lbl)] = str(val)
            self._api_to_label[str(val)] = str(lbl)
        self._attr_options = labels

    def _on_coordinator_update(self) -> None:
        self._sync_audio_class_options()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        if not self.available:
            return None
        if self.coordinator.data and "audio_alarm" in self.coordinator.data:
            audio_alarm = self.coordinator.data["audio_alarm"]
            if audio_alarm:
                api_value = audio_alarm.get("audioClass")
                if api_value is not None:
                    api_str = str(api_value)
                    display_value = self._api_to_label.get(api_str)
                    if display_value and display_value in self._attr_options:
                        return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        api_value = self._label_to_api.get(option)
        if api_value is None:
            return

        self._optimistic_value = option
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_audio_alarm, api_value, None, None, None
        )

        if success:
            await self.coordinator.async_request_refresh()
            if self.coordinator.data and self.coordinator.data.get(
                "audio_alarm", {}
            ).get("audioClass") == str(api_value):
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._sync_audio_class_options()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._on_coordinator_update)
        )


class HikvisionWarningSoundSelect(SelectEntity):
    """Select entity for warning sound (options from AudioAlarm/capabilities + fallbacks)."""

    _attr_unique_id = "hikvision_warning_sound"
    _attr_icon = "mdi:alert"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api, entry: ConfigEntry, host: str, device_name: str):
        """Initialize the select entity."""
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._entry = entry
        self._attr_name = f"{device_name} Warning Sound"
        self._attr_unique_id = f"{host}_warning_sound"
        self._optimistic_value = None
        self._label_to_id: dict[str, int] = {}
        self._id_to_label: dict[int, str] = {}
        self._attr_options: list[str] = []
        self._sync_warning_sound_options()

    def _sync_warning_sound_options(self) -> None:
        """Rebuild labels from coordinator capability snapshot."""
        norm = (self.coordinator.data or {}).get("audio_alarm_capabilities") or {}
        rows: list[dict] = [dict(r) for r in (norm.get("warning_sounds") or []) if isinstance(r, dict)]
        seen_ids = set()
        for r in rows:
            try:
                seen_ids.add(int(r["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        audio_alarm = (self.coordinator.data or {}).get("audio_alarm") or {}
        raw_cur = audio_alarm.get("audioID")
        if raw_cur is None:
            raw_cur = audio_alarm.get("alertAudioID")
        if raw_cur is not None:
            try:
                cur_id = int(raw_cur)
            except (TypeError, ValueError):
                cur_id = None
            if cur_id is not None and cur_id not in seen_ids:
                rows.append(
                    {"id": cur_id, "label": f"Sound #{cur_id} (current)"}
                )
        rows.sort(key=lambda r: int(r["id"]))

        self._label_to_id.clear()
        self._id_to_label.clear()
        labels: list[str] = []
        for row in rows:
            try:
                aid = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            lbl = str(row.get("label") or f"Sound {aid}")
            labels.append(lbl)
            self._label_to_id[lbl] = aid
            self._id_to_label[aid] = lbl
        self._attr_options = labels

    def _on_coordinator_update(self) -> None:
        self._sync_warning_sound_options()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        if not self.available:
            return None
        if self.coordinator.data and "audio_alarm" in self.coordinator.data:
            audio_alarm = self.coordinator.data["audio_alarm"]
            if audio_alarm:
                audio_id = audio_alarm.get("audioID")
                if audio_id is None:
                    audio_id = audio_alarm.get("alertAudioID")
                if audio_id is not None:
                    try:
                        aid = int(audio_id)
                    except (ValueError, TypeError):
                        return None
                    display_value = self._id_to_label.get(aid)
                    if display_value and display_value in self._attr_options:
                        return display_value
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        audio_id = self._label_to_id.get(option)
        if audio_id is None:
            return

        self._optimistic_value = option
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.api.set_audio_alarm, None, audio_id, None, None
        )

        if success:
            await self.coordinator.async_request_refresh()
            cur = self.coordinator.data.get("audio_alarm", {}) if self.coordinator.data else {}
            try:
                cur_raw = cur.get("audioID")
                if cur_raw is None:
                    cur_raw = cur.get("alertAudioID")
                cur_id = int(cur_raw) if cur_raw is not None else None
            except (ValueError, TypeError):
                cur_id = None
            if cur_id == audio_id:
                self._optimistic_value = None
        else:
            self._optimistic_value = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._sync_warning_sound_options()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._on_coordinator_update)
        )

