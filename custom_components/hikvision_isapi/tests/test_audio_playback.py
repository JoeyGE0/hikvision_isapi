"""Tests for Hikvision speaker audio conversion helpers."""
from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from custom_components.hikvision_isapi.audio_playback import (
    aac_silence_frame,
    build_ffmpeg_stream_command,
    pull_adts_frames,
)


def _adts_frame(length: int) -> bytes:
    header = bytearray(7)
    header[0] = 0xFF
    header[1] = 0xF1
    header[2] = 0x60
    header[3] = 0x40 | ((length >> 11) & 0x03)
    header[4] = (length >> 3) & 0xFF
    header[5] = ((length & 0x07) << 5) | 0x1F
    header[6] = 0xFC
    return bytes(header) + bytes(length - len(header))


def test_pull_adts_frames_across_chunks() -> None:
    """Complete frames are returned while partial data remains buffered."""
    first = _adts_frame(80)
    second = _adts_frame(90)
    stream = first + second
    buffer = bytearray(stream[:100])

    assert pull_adts_frames(buffer) == [first]
    assert bytes(buffer) == second[:20]

    buffer.extend(stream[100:])
    assert pull_adts_frames(buffer) == [second]
    assert not buffer


@patch(
    "custom_components.hikvision_isapi.audio_playback.find_ffmpeg",
    return_value="/usr/bin/ffmpeg",
)
def test_build_aac_stream_command(mock_find_ffmpeg) -> None:
    """AAC uses the proven codec, rate, padding, and ADTS output."""
    command = build_ffmpeg_stream_command(
        "http://ha.local/audio.mp3?token=secret",
        "AAC",
        sample_rate=16000,
        bitrate_k=64,
        start_seconds=1.25,
    )

    assert command[0] == "/usr/bin/ffmpeg"
    assert ["-ss", "1.250"] == command[4:6]
    assert "nobuffer" not in command
    assert "low_delay" not in command
    assert "adelay=250:all=1,apad=pad_dur=0.8" in command
    assert command[-1] == "pipe:1"
    assert command[command.index("-f") + 1] == "adts"
    assert command[command.index("-ar") + 1] == "16000"
    mock_find_ffmpeg.assert_called_once()


@patch(
    "custom_components.hikvision_isapi.audio_playback.find_ffmpeg",
    return_value="/usr/bin/ffmpeg",
)
def test_build_g711_alaw_stream_command(mock_find_ffmpeg) -> None:
    """G.711 A-law produces raw 8 kHz mono output."""
    command = build_ffmpeg_stream_command(
        "https://example.test/audio.wav", "G.711alaw"
    )

    assert command[command.index("-f") + 1] == "alaw"
    assert command[command.index("-ar") + 1] == "8000"
    assert "adts" not in command
    mock_find_ffmpeg.assert_called_once()


@patch(
    "custom_components.hikvision_isapi.audio_playback.find_ffmpeg",
    return_value="/usr/bin/ffmpeg",
)
def test_build_persistent_stream_command_without_padding(
    mock_find_ffmpeg,
) -> None:
    """Queue transitions can omit per-file lead and tail padding."""
    command = build_ffmpeg_stream_command(
        "https://example.test/audio.wav",
        "AAC",
        lead_silence_ms=0,
        tail_silence_s=0,
    )

    assert "-af" not in command
    mock_find_ffmpeg.assert_called_once()


@patch(
    "custom_components.hikvision_isapi.audio_playback.subprocess.run"
)
@patch(
    "custom_components.hikvision_isapi.audio_playback.find_ffmpeg",
    return_value="/usr/bin/ffmpeg",
)
def test_aac_silence_frame_is_generated_and_cached(
    mock_find_ffmpeg,
    mock_run,
) -> None:
    """The session keepalive reuses one valid encoded silence frame."""
    frame = _adts_frame(80)
    mock_run.return_value = CompletedProcess([], 0, frame, b"")
    aac_silence_frame.cache_clear()

    assert aac_silence_frame(16000, 64) == frame
    assert aac_silence_frame(16000, 64) == frame
    mock_run.assert_called_once()
    mock_find_ffmpeg.assert_called_once()
