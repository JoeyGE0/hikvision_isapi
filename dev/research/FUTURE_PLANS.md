# Hikvision ISAPI — future plans

Backlog for features we have researched but **not implemented yet**. Pick these up when back on the local network / after firmware updates.

---

## Issue #28 — G3 firmware V5.8.32+ features (animal, person status, alarm master)

| | |
|---|---|
| **GitHub issue** | [important new features in firmware V5.8.32_SP01 (260330) #28](https://github.com/JoeyGE0/hikvision_isapi/issues/28) |
| **Reporter** | [@andrewvbv](https://github.com/andrewvbv) — DS-2CD2387G3 on V5.8.32 SP1 |
| **Release note (H13)** | [Network_Camera-V5.8.32_SP1_260330_Release_Note-H13.pdf](https://assets.hikvision.com/prd/normal/all/files/202604/releasenote%5CNetwork_Camera-V5.8.32_SP1_260330_Release_Note-H13.pdf) |
| **Status** | Planned — **do not implement until home** (local camera probe required) |
| **Discussed** | 2026-06-23 |

### What is being asked?

Andrew upgraded a **DS-2CD2387G3** to **V5.8.32 SP1** and found new firmware capabilities:

1. **Animal detection** — perimeter smart events can target animals (release note: “perimeter animals and non-motor vehicles”; metadata may use `recognition: zoology`).
2. **Person status** — distinguish person **riding** vs **not riding** a non-motor vehicle (e.g. scooter/bike vs walking). Exact ISAPI event names / XML fields **not confirmed in our codebase yet**.
3. **Device Linkage Control (master alarm switches)** — global mute for **siren** (`notificationMethod: audio`) and **strobe** (`notificationMethod: whiteLight`) via:
   - `GET/PUT /ISAPI/System/status/disturbParams?format=json`
   - `disturbEnabled: true` = master **muted** (alarms suppressed globally)
   - `disturbEnabled: false` = master **armed** (alarms allowed)

### Owner preference (Josiah, 2026-06-23)

| Feature | Want? | Notes |
|---------|-------|-------|
| Animal + person ride / no-ride | **Yes** | Prefer simple `binary_sensor` entities for automations |
| Master siren / strobe mute switches | **Not now** | Worried about confusion next to existing **one siren entity + volume**; revisit later if a global “silence all cams” toggle is needed |
| Extra siren / trigger entities | **No** | Keep current siren entity as-is |

### Relevance to our cameras

| Camera | Model | Installed (last known) | Notes |
|--------|-------|------------------------|-------|
| Front Door, Driveway, Garage | `DS-2CD2387G3-LIS2UY` `/SL` or `/SRB` | V5.8.10 | **Target cams** for #28 after upgrade to **5.8.32** (`S3000732541` in archive) |
| Back Door, Backyard, Spa | `DS-2CD1383G2-LIUF` | V5.8.5 | Different line; animal/person features may not apply |

### Current integration gap

- No `disturbParams` API in `api.py`.
- `EVENTS` in `const.py` has no `animal` / person-ride event IDs.
- `HikvisionMotionTargetTypeSelect` options are only `human`, `vehicle`, `human,vehicle` — no `animal` / non-motor.
- Webhook parser (`notifications.py`) maps many aliases to `motiondetection` but does not fan out on `recognition` / target subtype yet.
- Existing **siren** (`siren.py`) = one-shot `trigger_audio_alarm` — **not** the same as master mute.

### Proposed implementation (when ready)

**Phase A — preferred first ship**

1. Read-only probe on a G3 at **5.8.32+** (Front Door `.11` or Garage `.13`):
   - `GET /ISAPI/Event/triggers`
   - Sample webhook XML when animal / person / non-motor events fire
   - Document exact `eventType` + `recognition` / property fields
2. If webhooks support it:
   - Add up to **3 binary sensors per cam** (feature-gated, same pattern as motion):
     - Animal
     - Person riding non-motor vehicle
     - Person not riding non-motor vehicle
   - Fire `hikvision_isapi_event` with subtype in event data for automations
3. Optionally extend **intrusion/line-crossing target** select to include `animal` (and non-motor if API exposes it).

**Phase B — deferred unless requested**

- Master **Alarm mute** switches (`disturbParams`) — 2 switches, clearly named (“Alarm master: siren mute”, “Alarm master: strobe mute”), **not** mixed with siren play/volume entity.

**Explicit non-goals**

- Do not add more siren entities or per-scenario alarm trigger buttons.
- Do not change advanced siren tone/volume behaviour (plain on/off restoring coordinator defaults shipped on `dev` 2026-06-29).

### Prerequisites before coding

- [ ] At home on LAN (or VPN) — `ha.teamclark.nz` / remote cannot query cameras directly
- [ ] At least one G3 updated to **V5.8.32** (archive row ready: `S3000732541`)
- [ ] Enable debug logging for `custom_components.hikvision_isapi.notifications`
- [ ] Trigger real events (walk, bike/scooter, pet if possible) and capture webhook XML
- [ ] Optional: run read-only ISAPI probe script against `.11` / `.13`

### Acceptance (draft)

- G3 on 5.8.32: animal/person binary sensors appear only when firmware sends matching events.
- Older firmware / 1383 cams: **no new entities** (no regression).
- Existing siren entity unchanged.
- Automations can use new binary sensors without extra alarm complexity.

### Related work already done

- Firmware archive manual rows for G3/1383 SKUs (separate repo).
- isapi v1.0.6 — firmware `applied_to` safety; unrelated to #28 detection features.

---

## Startup performance & HA quality — ~11s with 6 cameras (Spook)

| | |
|---|---|
| **Observed** | `hikvision_isapi` ~**11.6s** on HA boot (Spook “Integration startup times”) vs UniFi ~2.6s |
| **Status** | **Should fix** — works at 6 cams; **does not scale** (50 cams ≈ 50× archive downloads + probes) |
| **Discussed** | 2026-06-23 (audit against [HA integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)) |

### Scale reality check

**One config entry per camera** is correct for HA (`integration_type: device`). But work must **not** repeat per entry when the data is **shared** (firmware archive JSON is identical for every cam).

| Cameras | Firmware index today (worst case) | Risk |
|---------|-----------------------------------|------|
| 6 | ~66 MB download + 6× JSON parse on boot | Annoying (~11s Spook) |
| 50 | ~550 MB + 50× parse | **Would wreck HA** on every restart |

This is a design bug for large installs, not “fine until someone complains.”

### Is 11s “normal”?

**For this integration today: yes, expected.**  
**For HA high-quality integrations: no** — optional/diagnostic work is on the critical startup path.

Not a functional bug at 6 cams — it’s duplicated work per config entry:

| Per camera at startup (blocking) | Required? | HA-aligned? |
|----------------------------------|-----------|-------------|
| `get_device_info` + `get_capabilities` + `get_cameras` | **Yes** — test-before-setup | ✓ |
| `detect_features()` (~12+ **sequential** HTTP probes) | **Yes** — correct entity set, no 403 spam | Intent ✓, implementation slow |
| `get_supported_events()` (G2 fallback re-probes triggers) | **Yes** for event binary sensors | ✓ intent, duplicate probes ✗ |
| Main coordinator `async_config_entry_first_refresh()` | **Yes** — [documented HA pattern](https://developers.home-assistant.io/docs/integration_fetching_data/) | ✓, sequential polls slow |
| **Firmware update `await coordinator.async_refresh()`** | **No** — optional diagnostic entity | **✗ Not HA standard** |
| `set_alarm_server` + `ensure_http_alarm_notifications` | Debatable | Should defer to background |
| Boot retries `ISAPI_BOOT_RETRY_DELAYS` (20s + 40s) | When cam flaky | ✓; brutal if triggered |

### Why firmware archive runs on boot (and why it shouldn’t block)

`update.py` does this during platform setup:

```python
await coordinator.async_refresh()  # blocks until GitHub JSON downloaded
```

Each entry’s `FirmwareUpdateCoordinator._async_update_data()`:

1. Re-calls `get_device_info` (already fetched in `__init__.py`)
2. Downloads `firmware_index.json` (~11 MB)
3. On miss → also `firmwares_live.json` + `firmwares_manual.json`
4. Creates a **new** `aiohttp.ClientSession` per refresh (should use `async_get_clientsession(hass)` per [inject-websession](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/inject-websession/))

**Intent was good:** `async_refresh()` not `async_config_entry_first_refresh()` so archive outage doesn’t fail the whole integration. **Problem:** we still `await` it — blocks startup anyway.

**HA standard (e.g. ESPHome update entity):**

- Firmware/update metadata is **not** a prerequisite to prove the device works
- Optional update entities can be [`entity_registry_enabled_default = False`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-disabled-by-default/) (Gold)
- Coordinator polling “only if there are subscribers” — don’t force 11 MB fetch at setup
- Shared domain data across entries is OK ([HA core #115669](https://github.com/home-assistant/core/pull/115669)) — use `hass.data[DOMAIN]` for archive cache + locks

**Must block setup:** camera ISAPI + entity-correctness probes + main coordinator first refresh.  
**Must not block setup:** GitHub archive JSON, alarm-server reconfiguration, redundant `deviceInfo`.

### `quality_scale: gold` gaps (manifest claims gold today)

| Rule | Status |
|------|--------|
| Config flow, reauth, reconfigure, diagnostics | ✓ |
| Firmware update `EntityCategory.DIAGNOSTIC` | ✓ |
| `entity_registry_enabled_default = False` on firmware update | ✗ (ESPHome does this) |
| `PARALLEL_UPDATES` on platforms | ✗ **Silver** |
| `issue_tracker` in manifest | ✗ |
| `entry.runtime_data` vs legacy `hass.data[DOMAIN][entry_id]` | ✗ (Bronze+ recommends migration) |
| `async_get_clientsession` for archive HTTP | ✗ in `update.py` |
| Async camera client (`requests` in executor) | ✗ Platinum; OK for custom, not “max” |

Treat **gold** as aspirational until Silver items (at least `PARALLEL_UPDATES`) + startup fixes land.

### Implementation plan (priority order)

All **same behaviour** for users — no skipping feature detection.

#### Tier 1 — firmware archive (biggest win, required for scale)

1. **Shared archive cache** in `hass.data[DOMAIN]` — one fetch per HA boot / TTL, all entries read same parsed index
2. **Don’t `await` firmware refresh at setup** — add update entity, `async_create_task(coordinator.async_refresh())`; brief `unknown` is fine
3. **`async_get_clientsession(hass)`** for archive downloads
4. Stop re-fetching `get_device_info` in firmware coordinator when `device_info` already in entry data
5. Consider `_attr_entity_registry_enabled_default = False` on firmware update (Gold)

#### Tier 2 — camera path (faster, still required)

6. Reuse capabilities XML in `detect_features` (no second `/ISAPI/System/capabilities`)
7. Parallel independent `_test_endpoint_exists` probes (thread pool inside executor)
8. Deduplicate `get_supported_events` fallback vs `detect_features` probe paths
9. `asyncio.gather` batches in main coordinator `_async_update_data` / first refresh

#### Tier 3 — Gold housekeeping

10. `PARALLEL_UPDATES` on all platforms (`0` for coordinator platforms, `1` for action platforms)
11. Migrate to typed `entry.runtime_data` dataclass
12. Add `issue_tracker` to manifest
13. Defer alarm-server writes to background task after setup completes

### Non-goals

- Don’t remove feature probing (403 spam / wrong entities on G2).
- Don’t merge all cams into one config entry.
- Don’t drop firmware update entity — defer + share, don’t delete.
- Don’t block startup on archive or alarm-server failures.

### Acceptance (draft)

- **6 cams:** integration startup **&lt;5s** (Spook) after Tier 1+2.
- **50 cams:** **one** archive download per boot; startup scales with per-cam ISAPI only, not ×50 GitHub JSON.
- Firmware entities populate within ~30s after boot without blocking integration ready.
- No change to runtime polling, webhooks, or OTA install behaviour.
- Single-camera installs unchanged or faster.

### References

- Audit chat: 2026-06-23
- Code: `__init__.py` (setup), `coordinator.py` (first refresh), `update.py` (firmware coordinator)
- [Fetching data](https://developers.home-assistant.io/docs/integration_fetching_data/) · [test-before-setup](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/) · [entity-disabled-by-default](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-disabled-by-default/)

---

## Config flow — Basic vs Advanced entity profiles

| | |
|---|---|
| **Status** | Idea — Josiah wants this next (2026-06-29) |
| **Goal** | Less overwhelming setup; power users opt in |

### Concept

1. **Basic (default)** — config flow offers motion, camera stream, alarm/siren if supported, restart, and a small “main things” set. User ignores advanced → simple install.
2. **Advanced** — same as today: expose everything the cam supports; entities that are disabled-by-default now start **unselected**; user ticks what to add from a checklist.
3. **Later** — reconfigure integration to add/remove entity groups; or disable individual entities in the registry.

### Non-goals (draft)

- Don’t remove entities from codebase — only change defaults and config-flow UX.
- Don’t auto-enable speaker / warning-sound / diagnostic entities in Basic mode.

### References

- Many entities already use `entity_registry_enabled_default = False` (speaker, warning sound, etc.) — Advanced mode can mirror that pattern at setup time.

---

## AAC two-way / file play to speaker (researched 2026-07-15)

| | |
|---|---|
| **Status** | Researched locally — **not implemented** in integration yet |
| **Doc** | [AAC_FILE_PLAYBACK_AND_STABILITY.md](./AAC_FILE_PLAYBACK_AND_STABILITY.md) |
| **go2rtc PR draft** | `dev/tools/backyard_aac_talk/GO2RTC_AAC_PR.md` |
| **Lab** | `dev/tools/backyard_aac_talk/` |

**Proven:** ISAPI AAC talk + file play on Backyard (1383, 5.8.41) using `[u32be len][ADTS]` @ 16 kHz. Volume XML swap still applies (`microphoneVolume` = loudspeaker).

**Later HA work:** ✅ started — `media_player` + `api.play_audio_bytes` convert via ffmpeg and stream AAC (`[u32be len][ADTS]`) or G.711 (see `audio_playback.py`). Still verify on cam + polish STOP/session edge cases.  
**Parallel:** fork go2rtc ISAPI client for AAC so Frigate/`isapi://` talk works on AAC-default cams.

**Stability takeaway:** talk uses **TwoWayAudio** bitrate/sample-rate (not RTSP stream video bitrate). On probed cam AAC sample rate is **locked to 16 kHz**; BR 16/32/64 OK.

---

## Other future ideas

| ID | Topic | Link | Status |
|----|-------|------|--------|
| — | Archive scraper: fix `supported_models` merge in `main.py` | hikvision-fw-archive | Idea — auto rows for new SKUs |
| — | Basic vs Advanced config-flow entity profiles | this file | Idea — next UX pass |
| — | AAC file play + go2rtc AAC talk | AAC_FILE_PLAYBACK_AND_STABILITY.md | Researched — implement another day |
