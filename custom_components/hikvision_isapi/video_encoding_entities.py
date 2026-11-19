"""Shared base for the video encoding (beta) select/number entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN, ENTITY_GROUP_VIDEO_ENCODING, STREAM_TYPE
from .device_helpers import get_primary_device_info, patch_coordinator_section
from .entity_profiles import entity_enabled

_LOGGER = logging.getLogger(__name__)


def stream_label(stream_id: int) -> str:
    """'Main Stream' / 'Sub-stream' / ... for a stream id like 101."""
    return STREAM_TYPE.get(stream_id % 100, f"Stream {stream_id}")


def video_encoding_targets(hass, entry: ConfigEntry, item_id: str) -> list[int]:
    """Stream ids to create an entity for (empty when the item is off)."""
    data = hass.data[DOMAIN][entry.entry_id]
    if not data.get("detected_features", {}).get("video_encoding", False):
        return []
    if not entity_enabled(entry, ENTITY_GROUP_VIDEO_ENCODING, item_id):
        return []
    return list(getattr(data["api"], "video_encoding_stream_ids", None) or [])


class VideoEncodingEntityMixin:
    """Coordinator wiring + write helper shared by the beta encoder entities."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.CONFIG

    def _init_video_encoding(
        self,
        coordinator,
        api,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        stream_id: int,
        key: str,
        label: str,
    ) -> None:
        self.coordinator = coordinator
        self.api = api
        self._entry = entry
        self._host = host
        self._stream_id = stream_id
        self._attr_name = f"{device_name} {stream_label(stream_id)} {label}"
        self._attr_unique_id = f"{host}_{key}_{stream_id}"
        # Sub/third streams are usually only used for detection: off by default.
        self._attr_entity_registry_enabled_default = stream_id % 100 == 1
        self._optimistic_value: Any = None

    @property
    def device_info(self) -> DeviceInfo:
        return get_primary_device_info(self.coordinator.hass, self._entry)

    @property
    def stream_data(self) -> dict:
        data = (self.coordinator.data or {}).get("video_encoding") or {}
        stream = data.get(self._stream_id)
        if stream is None:
            stream = data.get(str(self._stream_id))
        return stream if isinstance(stream, dict) else {}

    @property
    def caps(self) -> dict:
        return self.api.get_video_encoding_caps_cached(self._stream_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stream = self.stream_data
        return {
            "stream_id": self._stream_id,
            "codec": stream.get("codec"),
            "bitrate_type": stream.get("control_type"),
            "smart_codec": stream.get("smart_codec"),
            "beta": True,
        }

    async def _async_write(self, **changes) -> None:
        entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
        lock = entry_data.get("api_lock")
        try:
            if lock is not None:
                async with lock:
                    result = await self.hass.async_add_executor_job(
                        lambda: self.api.set_video_encoding(self._stream_id, **changes)
                    )
            else:
                result = await self.hass.async_add_executor_job(
                    lambda: self.api.set_video_encoding(self._stream_id, **changes)
                )
        except (ValueError, RuntimeError) as err:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"{self.name}: {err}") from err
        except Exception as err:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"{self.name}: camera rejected the change ({err})") from err

        self._optimistic_value = None
        current = dict((self.coordinator.data or {}).get("video_encoding") or {})
        current[self._stream_id] = result
        data = self.coordinator.data
        if isinstance(data, dict):
            self.coordinator.async_set_updated_data({**data, "video_encoding": current})
        else:
            patch_coordinator_section(self.coordinator, "video_encoding", current)

    @property
    def should_poll(self) -> bool:
        return False

    async def async_update(self) -> None:
        """homeassistant.update_entity: re-read the camera now (picks up mode changes)."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
