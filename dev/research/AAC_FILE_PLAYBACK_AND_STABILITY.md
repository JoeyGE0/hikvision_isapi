# AAC file playback over ISAPI + bitrate/sample-rate stability

**Date:** 2026-07-15  
**Camera:** Backyard `192.168.1.15` — `DS-2CD1383G2-LIUF/SL` fw **V5.8.41**  
**Purpose:** Notes for a future `hikvision_isapi` “play audio file to cam speaker” feature, and for forking go2rtc ISAPI talk (AAC).  
**Lab tool:** `dev/tools/backyard_aac_talk/` (live mic) + one-shot file send (same wire format).

---

## How we played an audio file (working method)

Confirmed: ~3s of `top-g-theme.mp3` played on the Backyard loudspeaker at **5%**.

### 1) Transcode to what the talk channel expects

ffmpeg → **AAC-LC ADTS**, mono, **16 kHz**, ~64 kbps:

```bash
ffmpeg -t 3 -i input.mp3 -ac 1 -ar 16000 -c:a aac -profile:a aac_low -b:a 64k -f adts out.aac
```

### 2) Session (same as G.711 talk in `api.py`)

1. Backup `GET /ISAPI/System/TwoWayAudio/channels/1`
2. Set loudspeaker volume via **`microphoneVolume`** (XML names swapped on these cams — same as HA integration)
3. `PUT .../close` → sleep ~0.3s → `PUT .../open` → parse `<sessionId>`
4. Stream to `PUT /ISAPI/System/TwoWayAudio/channels/1/audioData?sessionId=...`
5. `PUT .../close`
6. Restore the saved channel XML

### 3) Wire format (critical — not in ISAPI PDF)

Camera GET mic stream and our successful PUT both use:

```text
[uint32 big-endian length][ADTS AAC frame]  (repeat)
```

Not raw ADTS-only. Not RTP.

### 4) Pacing

- AAC-LC frame = **1024 samples**
- @ **16 kHz** → **64 ms** per frame
- Deadline pacing (sleep only if ahead); same idea as HA G.711 chunk sleeps, different unit

### 5) Volume

| XML field | On this firmware means |
|-----------|------------------------|
| `microphoneVolume` | Talk **loudspeaker** % |
| `speakerVolume` | Cam **mic gain** % |

File play test used `microphoneVolume=5`.

### Implementation hint (HA / go2rtc later)

- Prefer `audioCompressionType=AAC` on cams that open AAC sessions successfully.
- Always encode **to match** `audioSamplingRate` from the channel GET (here always **16** for AAC).
- Length-prefix every ADTS frame before write.
- Do **not** double-pace (don’t realtime-buffer *and* sleep 64 ms).

Dev lab: `dev/tools/backyard_aac_talk/`.

---

## Camera config vs stream config (don’t confuse them)

| Setting | Endpoint | Affects 2-way talk? |
|---------|----------|---------------------|
| Talk codec / `audioBitRate` / `audioSamplingRate` | `/ISAPI/System/TwoWayAudio/channels/1` | **Yes** |
| RTSP channel audio codec | `/ISAPI/Streaming/channels/101` `Audio` | **No** (listen path / Frigate) |
| RTSP video bitrate | same StreamingChannel `Video` | **No** |

Backyard RTSP `101`/`102` audio was already AAC; changing main-stream **video** CBR 8192→2048 did **not** break AAC talk (session open + full frame send OK). Restored to 8192 after test.

---

## Accepted TwoWayAudio values (probe, AAC)

Capabilities list many codecs; channel GET also shows `audioBitRate` / `audioSamplingRate` (not in capabilities XML opts).

### `audioSamplingRate` (AAC)

| PUT value | Result |
|-----------|--------|
| **16** | **200**, sticks |
| 8, 11, 12, 22, 24, 32, 44, 48 | **503** — stays 16 |

**Fork rule:** treat talk AAC as **16 kHz fixed** on this model/fw. Don’t invent 8/48 kHz talk.

### `audioBitRate` (AAC)

| PUT value | Result |
|-----------|--------|
| **16, 32, 64** | **200**, sticks |
| 24, 256 | 200 but **snaps back to 64** |
| 8, 48, 96, 128, 160, 192 | **503** |

### Codecs (PUT accepted)

`AAC`, `G.711ulaw`, `G.711alaw`, `G.726`, `PCM`, `G.722.1`, `MP2L2` all return HTTP 200.

**Open session caveat (this cam):** after setting `G.711ulaw`, `PUT .../open` returned **403 Invalid Operation**. AAC open still **200**. So “codec listed ≠ talk session works.” go2rtc must open/check, not only trust opts.

---

## File-play matrix (2026-07-15)

Each row: set channel → open → PUT length-prefixed ADTS (~2.5s clip) → close. Loudspeaker 5%.  
**Hearing:** Josiah confirmed an earlier matched 64k/16k play worked. Later matrix rows are **transport-only** unless re-listened.

| Test | Cam setting | File | Transport | Notes for fork |
|------|-------------|------|-----------|----------------|
| Baseline | AAC 64 / 16 | 64k @ 16 kHz | 41/41 OK | Golden path |
| Matched BR | AAC 16 / 16 | 16k @ 16 kHz | 41/41 OK | Lower BR OK |
| Matched BR | AAC 32 / 16 | 32k @ 16 kHz | 41/41 OK | Mid BR OK |
| BR mismatch | AAC **16** / 16 | **64k** @ 16 kHz | 41/41 OK | Encoder BR need not equal XML BR for HTTP send |
| SR mismatch | AAC 16 / 16 | 16k @ **8 kHz** | 21/21 OK | May sound wrong; **don’t use** in product |
| SR mismatch | AAC 64 / 16 | 64k @ **48 kHz** | 119/119 OK | May sound wrong; **don’t use** |
| Wrong codec | **G.711ulaw** | AAC file | open **403**, broken pipe | Codec must match **and** open must succeed |
| RTSP video BR change | AAC 64 / 16 | 64k @ 16 kHz | 41/41 OK | Video stream bitrate irrelevant to talk |

**Stable defaults for forked go2rtc / future HA file play:**

1. Force talk channel `audioCompressionType=AAC`, `audioSamplingRate=16`, `audioBitRate=64` (or read-back and match encode SR).
2. Encode/transcode WebRTC/Opus → **AAC-LC 16 kHz mono ADTS**.
3. Wrap each frame: `u32be(len) + adts`.
4. Pace ≈ `1024 / sample_rate` seconds.
5. Fail talk setup if `open` ≠ 200 (don’t assume G.711 works because caps say so).

---

## go2rtc gap (why fork)

Upstream go2rtc `pkg/isapi` only allows `G.711ulaw` / `G.711alaw` and has no AAC ADTS length-prefix path. On this Backyard unit, **AAC is the working talk codec**; G.711 open was rejected in probe.

Draft PR text: `dev/tools/backyard_aac_talk/GO2RTC_AAC_PR.md`.

---

## Future HA integration (file play — not started)

Suggested later work in `hikvision_isapi`:

- Service e.g. `hikvision_isapi.play_audio` / media_player style: path or URL → ffmpeg → ISAPI AAC PUT
- Reuse existing open/close + **swapped volume** helpers in `api.py`
- Never leave channel at test volumes; always restore XML
- Gate on channel `audioCompressionType` / successful `open`

---

## Restore state after tests

Verified after matrix:

- TwoWayAudio: AAC, BR 64, SR 16, speakerVol 20, micVol 30  
- Streaming 101 video CBR: **8192**
