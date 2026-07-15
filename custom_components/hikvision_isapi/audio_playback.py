"""Convert and frame audio for Hikvision ISAPI two-way talk.

Wire format matches the backyard AAC lab and JoeyGE0/go2rtc ISAPI client:
- AAC: ``[uint32 BE length][ADTS frame]`` paced at ``1024 / sample_rate`` seconds
- G.711: raw PCMU/PCMA chunks (no length prefix), paced by chunk / 8000

Any input ffmpeg understands (mp3, wav, m4a, opus, etc.) is transcoded to the
camera's TwoWayAudio compression type before streaming.
"""
from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
import tempfile
from typing import Iterable

_LOGGER = logging.getLogger(__name__)

AAC_SAMPLES_PER_FRAME = 1024
DEFAULT_AAC_SAMPLE_RATE = 16000
DEFAULT_AAC_BITRATE_K = 64

_FFMPEG_CANDIDATES = (
    "ffmpeg",
    "/usr/lib/ffmpeg/7.0/bin/ffmpeg",
    "/usr/lib/ffmpeg/5.0/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
)


def find_ffmpeg() -> str:
    """Locate ffmpeg (same candidate order as go2rtc ISAPI talk)."""
    for candidate in _FFMPEG_CANDIDATES:
        path = shutil.which(candidate)
        if path:
            return path
        if candidate.startswith("/") and os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "ffmpeg not found — required to convert media for camera speaker playback"
    )


def split_adts(data: bytes) -> list[bytes]:
    """Split an ADTS bitstream into frames (lab / go2rtc)."""
    frames: list[bytes] = []
    i = 0
    while i + 7 <= len(data):
        if data[i] != 0xFF or (data[i + 1] & 0xF0) != 0xF0:
            i += 1
            continue
        protection_absent = data[i + 1] & 0x01
        hdr = 7 if protection_absent else 9
        frame_len = (
            ((data[i + 3] & 0x03) << 11)
            | (data[i + 4] << 3)
            | ((data[i + 5] & 0xE0) >> 5)
        )
        if frame_len < hdr or i + frame_len > len(data):
            i += 1
            continue
        frames.append(data[i : i + frame_len])
        i += frame_len
    return frames


def normalize_sample_rate(raw: object | None, default: int = DEFAULT_AAC_SAMPLE_RATE) -> int:
    """Hikvision often reports ``16`` meaning 16 kHz."""
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    if value < 1000:
        return value * 1000
    return value


def compression_is_aac(compression: str | None) -> bool:
    return bool(compression) and "aac" in compression.lower()


def compression_is_alaw(compression: str | None) -> bool:
    return bool(compression) and "alaw" in compression.lower()


def ffmpeg_convert_to_adts(
    audio_bytes: bytes,
    *,
    sample_rate: int = DEFAULT_AAC_SAMPLE_RATE,
    bitrate_k: int = DEFAULT_AAC_BITRATE_K,
) -> bytes:
    """Transcode arbitrary audio to AAC-LC ADTS mono (lab / go2rtc)."""
    return _ffmpeg_file_convert(
        audio_bytes,
        [
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-b:a",
            f"{bitrate_k}k",
            "-f",
            "adts",
        ],
    )


def ffmpeg_convert_to_g711(
    audio_bytes: bytes,
    *,
    alaw: bool = False,
) -> bytes:
    """Transcode arbitrary audio to G.711 µ-law or A-law @ 8 kHz mono."""
    fmt = "alaw" if alaw else "mulaw"
    return _ffmpeg_file_convert(
        audio_bytes,
        [
            "-ar",
            "8000",
            "-ac",
            "1",
            "-f",
            fmt,
        ],
    )


def _ffmpeg_file_convert(audio_bytes: bytes, output_args: list[str]) -> bytes:
    if not audio_bytes:
        raise ValueError("empty audio input")

    ffmpeg = find_ffmpeg()
    # Temp file so ffmpeg can probe any container (mp3/wav/m4a/…) reliably.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            tmp_path,
            *output_args,
            "pipe:1",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=120,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err}")
        if not proc.stdout:
            raise RuntimeError("ffmpeg produced no audio output")
        return proc.stdout
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def iter_aac_isapi_packets(adts_data: bytes) -> Iterable[bytes]:
    """Yield length-prefixed ADTS packets for ISAPI PUT audioData."""
    for frame in split_adts(adts_data):
        yield struct.pack(">I", len(frame)) + frame


def aac_frame_duration_s(sample_rate: int) -> float:
    return AAC_SAMPLES_PER_FRAME / float(sample_rate or DEFAULT_AAC_SAMPLE_RATE)
