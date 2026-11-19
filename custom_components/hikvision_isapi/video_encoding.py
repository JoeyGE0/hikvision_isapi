"""Video encoder (bitrate / picture quality) helpers for /ISAPI/Streaming/channels/<id>.

Beta. Behaviour verified on DS-2CD1383G2-LIUF (V5.8.41) and DS-2CD2387G3 (V5.8.40):

- VBR: the real cap is ``vbrUpperCap``. ``constantBitRate`` is ignored and the
  camera mirrors it to the upper cap.
- CBR: the real rate is ``constantBitRate``. ``vbrUpperCap`` is not returned.
  ``fixedQuality`` is kept but has no effect.
- H.265+ / H.264+ (``SmartCodec`` enabled): adds ``vbrAverageCap`` (average
  bitrate). In VBR the camera silently keeps the old average when the new one is
  above the max bitrate, so callers must keep average <= max.
- ``fixedQuality`` only takes the values listed in capabilities
  (1/20/40/60/80/100); anything else is silently rounded down.
- A bitrate above the capability max is rejected (deviceError).

The PUT is GET-modify-PUT of the full StreamingChannel document so every other
stream setting (resolution, fps, GOP, codec, audio, ...) is preserved.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"

# Hikvision web UI names for fixedQuality.
QUALITY_LABELS: dict[int, str] = {
    1: "Lowest",
    20: "Lower",
    40: "Low",
    60: "Medium",
    80: "Higher",
    100: "Highest",
}
QUALITY_VALUES: dict[str, int] = {label: value for value, label in QUALITY_LABELS.items()}

DEFAULT_QUALITY_OPTIONS: tuple[int, ...] = (1, 20, 40, 60, 80, 100)
DEFAULT_BITRATE_MIN = 32
DEFAULT_BITRATE_MAX = 16384


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_video(root: ET.Element) -> ET.Element | None:
    if _local(root.tag) == "Video":
        return root
    for elem in root.iter():
        if _local(elem.tag) == "Video":
            return elem
    return None


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in parent:
        if _local(child.tag) == name:
            return child
    return None


def _int(elem: ET.Element | None) -> int | None:
    if elem is None or elem.text is None:
        return None
    try:
        return int(elem.text.strip())
    except ValueError:
        return None


def _text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    return elem.text.strip()


def quality_label(value: int | None) -> str | None:
    """fixedQuality number -> web UI label (unknown values shown as the number)."""
    if value is None:
        return None
    return QUALITY_LABELS.get(value, str(value))


def parse_video_encoding(xml_text: str) -> dict[str, Any]:
    """Parse a StreamingChannel GET into the fields HA cares about."""
    root = ET.fromstring(xml_text)
    video = _find_video(root)
    if video is None:
        return {}
    smart = _child(video, "SmartCodec")
    smart_enabled = _text(_child(smart, "enabled"))
    control = _text(_child(video, "videoQualityControlType"))
    data: dict[str, Any] = {
        "codec": _text(_child(video, "videoCodecType")),
        "control_type": control.upper() if control else None,
        "quality": _int(_child(video, "fixedQuality")),
        "constant_bitrate": _int(_child(video, "constantBitRate")),
        "vbr_upper_cap": _int(_child(video, "vbrUpperCap")),
        "vbr_average_cap": _int(_child(video, "vbrAverageCap")),
        "smart_codec": (smart_enabled or "").lower() == "true",
        "width": _int(_child(video, "videoResolutionWidth")),
        "height": _int(_child(video, "videoResolutionHeight")),
        "max_frame_rate": _int(_child(video, "maxFrameRate")),
    }
    data["max_bitrate"] = effective_max_bitrate(data)
    return data


def effective_max_bitrate(data: dict[str, Any]) -> int | None:
    """The bitrate the camera actually uses as its ceiling (web UI 'Max. Bitrate')."""
    if data.get("control_type") == "VBR" and data.get("vbr_upper_cap") is not None:
        return data["vbr_upper_cap"]
    return data.get("constant_bitrate")


def parse_video_encoding_caps(xml_text: str) -> dict[str, Any]:
    """Parse /capabilities for quality options and bitrate range."""
    caps: dict[str, Any] = {
        "quality_options": list(DEFAULT_QUALITY_OPTIONS),
        "bitrate_min": DEFAULT_BITRATE_MIN,
        "bitrate_max": DEFAULT_BITRATE_MAX,
        "control_types": ["CBR", "VBR"],
    }
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return caps
    video = _find_video(root)
    if video is None:
        return caps

    quality = _child(video, "fixedQuality")
    if quality is not None and quality.get("opt"):
        opts = []
        for raw in quality.get("opt", "").split(","):
            raw = raw.strip()
            if raw.isdigit():
                opts.append(int(raw))
        if opts:
            caps["quality_options"] = sorted(set(opts))

    mins: list[int] = []
    maxes: list[int] = []
    for tag in ("constantBitRate", "vbrUpperCap"):
        elem = _child(video, tag)
        if elem is None:
            continue
        try:
            if elem.get("min") is not None:
                mins.append(int(elem.get("min")))
            if elem.get("max") is not None:
                maxes.append(int(elem.get("max")))
        except ValueError:
            continue
    if mins:
        caps["bitrate_min"] = max(mins)
    if maxes:
        caps["bitrate_max"] = min(maxes)

    control = _child(video, "videoQualityControlType")
    if control is not None and control.get("opt"):
        caps["control_types"] = [o.strip().upper() for o in control.get("opt").split(",") if o.strip()]
    return caps


def _replace_tag(xml_text: str, tag: str, value: int) -> str:
    new_text, count = re.subn(
        rf"(<{tag}(?:\s[^>]*)?>)\s*[^<]*\s*(</{tag}>)",
        rf"\g<1>{value}\g<2>",
        xml_text,
        count=1,
    )
    if count == 0:
        raise ValueError(f"<{tag}> not found in StreamingChannel XML")
    return new_text


def build_video_encoding_put(
    xml_text: str,
    *,
    quality: int | None = None,
    max_bitrate: int | None = None,
    average_bitrate: int | None = None,
    caps: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (new XML, expected parsed values) for a change.

    Raises ValueError for values the camera would reject or silently ignore.
    """
    caps = caps or {}
    current = parse_video_encoding(xml_text)
    if not current:
        raise ValueError("No <Video> section in StreamingChannel XML")

    bitrate_min = int(caps.get("bitrate_min", DEFAULT_BITRATE_MIN))
    bitrate_max = int(caps.get("bitrate_max", DEFAULT_BITRATE_MAX))
    quality_options = list(caps.get("quality_options") or DEFAULT_QUALITY_OPTIONS)

    new_xml = xml_text
    expected: dict[str, Any] = {}
    control = current.get("control_type")
    max_now = current.get("max_bitrate")

    if quality is not None:
        quality = int(quality)
        if quality not in quality_options:
            raise ValueError(
                f"Picture quality {quality} not supported (allowed: {quality_options})"
            )
        new_xml = _replace_tag(new_xml, "fixedQuality", quality)
        expected["quality"] = quality

    if max_bitrate is not None:
        max_bitrate = int(max_bitrate)
        if not bitrate_min <= max_bitrate <= bitrate_max:
            raise ValueError(
                f"Max bitrate {max_bitrate} kbps out of range {bitrate_min}-{bitrate_max}"
            )
        new_xml = _replace_tag(new_xml, "constantBitRate", max_bitrate)
        if control == "VBR" and current.get("vbr_upper_cap") is not None:
            new_xml = _replace_tag(new_xml, "vbrUpperCap", max_bitrate)
        expected["max_bitrate"] = max_bitrate
        max_now = max_bitrate
        # Average must stay <= max or the camera silently ignores later changes.
        avg = current.get("vbr_average_cap")
        if (
            average_bitrate is None
            and current.get("smart_codec")
            and avg is not None
            and avg > max_bitrate
        ):
            average_bitrate = max_bitrate

    if average_bitrate is not None:
        average_bitrate = int(average_bitrate)
        if current.get("vbr_average_cap") is None:
            raise ValueError(
                "Average bitrate only exists with H.265+/H.264+ (Smart Codec) enabled"
            )
        if average_bitrate < bitrate_min:
            raise ValueError(f"Average bitrate must be at least {bitrate_min} kbps")
        if max_now is not None and average_bitrate > max_now:
            raise ValueError(
                f"Average bitrate {average_bitrate} kbps can't be above max bitrate {max_now} kbps"
            )
        new_xml = _replace_tag(new_xml, "vbrAverageCap", average_bitrate)
        expected["vbr_average_cap"] = average_bitrate

    return new_xml, expected


def mismatched_fields(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """Fields the camera did not apply (it often answers OK but keeps old values)."""
    return {
        key: (want, actual.get(key))
        for key, want in expected.items()
        if actual.get(key) != want
    }
