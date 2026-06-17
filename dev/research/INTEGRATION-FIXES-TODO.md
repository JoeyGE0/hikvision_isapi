# Hikvision ISAPI — integration fixes TODO

Backlog of reliability bugs and suggested fixes identified during siren/alarm investigation (June 2026).

**Already shipped (commit `a4ba8a2`):** siren tone verification, explicit `_active_tone_id` in retrigger loop, `audioIsPlayingPleaseWait` treated as success, normalized tone matching, integer tone prefers audio ID over list index.

---

## Priority summary

| Priority | # | Issue | Relevant to standalone cameras + sirens |
|----------|---|-------|----------------------------------------|
| **P0 — do first** | 1, 5 | Siren loop survives reload; turn_on overwrites turn_off | Yes — “power cycle” / siren won’t stop |
| **P1 — soon** | 6, 7 | 403 → false reauth; no API lock | Yes — busy siren / reauth nag |
| **P2 — correctness** | 2 | Binary sensor webhook bypasses entity | Motion automations OK; UI icons fragile |
| **P3 — edge cases** | 8, 9, 10, 11–15 | DNS, reload race, media player, misc | Lower unless using speaker entity |
| **Skip unless NVR** | 3 | NVR wrong channel fallback | No |
| **Skip unless alarm inputs** | 4 | IO sensors gated on Event/triggers API | Only if wired physical inputs |

---

## P0 — Siren

### 1. Siren loop survives reload/unload

**Files:** `custom_components/hikvision_isapi/siren.py`

**Problem:** The siren retriggers via a background `asyncio` task (`_async_trigger_loop`). There is no `async_will_remove_from_hass`, so integration reload or entity removal does not call `async_turn_off`. The loop can become an orphan and keep PUTting to the camera.

- Full HA restart kills the process — OK.
- Integration reload / config entry reload — loop may survive.

**Suggested fix:**

- [ ] Add `async_will_remove_from_hass` → `await self.async_turn_off()`
- [ ] Add `_turn_generation: int` counter (see #5)
- [ ] After each `trigger_audio_alarm` in the loop, check `_stop_event.is_set()` before sleeping
- [ ] Optional: debug log on turn_off with generation number

**Acceptance:** Reload integration while siren is on → no further HTTP triggers to camera after unload completes.

---

### 5. Siren `turn_off` vs in-flight `turn_on` (race)

**Files:** `custom_components/hikvision_isapi/siren.py`

**Problem:** `async_turn_on` does slow HTTP (`set_audio_alarm`, GET confirm) before starting the loop. Timeline:

1. Automation turns siren **on** → `turn_on` starts
2. User/automation turns siren **off** → `turn_off` runs; no loop yet to cancel; `is_on=False`
3. Original `turn_on` **finishes** → sets `is_on=True`, starts **new** loop

Result: siren keeps going after turn_off. Likely contributor to “had to power cycle” reports.

**Note:** One extra HTTP trigger after `turn_off` (in-flight request) is acceptable — camera has no stop endpoint; last clip may finish.

**Suggested fix:**

- [ ] At start of `async_turn_on`: `self._turn_generation += 1`; capture `my_gen = self._turn_generation`
- [ ] After all slow HTTP and after the intentional `await self.async_turn_off()` at line ~178, bail if `my_gen != self._turn_generation`
- [ ] Pass `my_gen` into `_async_trigger_loop`; exit loop if generation changed
- [ ] In `async_turn_off`: increment generation (or rely on next turn_on increment — pick one consistent scheme)

**Acceptance:** Call `turn_off` while `turn_on` is still in progress → loop never starts; siren stops retriggers.

---

## P1 — API / auth reliability

### 6. 403 treated as authentication failure

**Files:** `custom_components/hikvision_isapi/api.py`, `custom_components/hikvision_isapi/coordinator.py`

**Problem:** HTTP **401** = wrong password. HTTP **403** can mean many things: missing permission, endpoint busy, `audioIsPlayingPleaseWait` (clip still playing). Code raises `AuthenticationError` for all 403s → coordinator calls `entry.async_start_reauth()` → HA prompts for password even when credentials are correct.

**Suggested fix:**

- [ ] **401 only** → raise `AuthenticationError` (triggers reauth)
- [ ] **403** → parse `subStatusCode` / error message:
  - If `audioIsPlayingPleaseWait` → return success / `False` without reauth (siren `trigger_audio_alarm` already does this locally)
  - Otherwise → log warning, return `False`; do **not** raise `AuthenticationError`
- [ ] Consider new exception type e.g. `PermissionError` or `APIBusyError` for coordinator logging without reauth
- [ ] Coordinator: only `async_start_reauth` on `AuthenticationError`, not generic 403

**Acceptance:** Siren busy / permission-denied on optional endpoint does not open reauth flow.

---

### 7. No API lock (concurrent camera access)

**Files:** `custom_components/hikvision_isapi/__init__.py`, `api.py` (call sites), `coordinator.py`, `siren.py`, platform modules

**Problem:** Coordinator poll, siren retrigger loop, switches, selects, media player, etc. all hit the same camera concurrently. Firmware can return transient 403 busy states or failed PUTs.

**Suggested fix:**

- [ ] Create `asyncio.Lock()` per config entry in `hass.data[DOMAIN][entry_id]["api_lock"]` at setup
- [ ] Wrap executor API calls that mutate or poll camera state:
  ```python
  async with data["api_lock"]:
      await hass.async_add_executor_job(api.method, ...)
  ```
- [ ] Minimum: coordinator refresh + siren loop + write platforms (switch/select/number/siren turn_on)
- [ ] Optional: separate read/write locks if lock contention becomes an issue

**Acceptance:** Fewer `audioIsPlayingPleaseWait` / busy 403s under siren + coordinator load.

---

## P2 — Binary sensors / webhooks

### 2. Webhook bypasses binary sensor entity

**Files:** `custom_components/hikvision_isapi/notifications.py`, `custom_components/hikvision_isapi/binary_sensor.py`

**Problem:** Webhook calls `hass.states.async_set(entity_id, STATE_ON/OFF)` directly. That updates HA’s state machine (automations often work) but **not** the entity’s `_attr_is_on`. Icon property reads `_attr_is_on` → UI can show wrong icon. Coordinator `async_write_ha_state()` can snap motion back to OFF while webhook had it ON.

**Suggested fix:**

- [ ] Add `EventBinarySensor.async_handle_alert(self, active: bool)`:
  - Set `self._attr_is_on = active`
  - Call `self.async_write_ha_state()`
  - Fire `HIKVISION_EVENT` on transition to ON (move from webhook)
- [ ] In `trigger_sensor`, resolve entity via entity platform or registry + lookup live entity instance; call `async_handle_alert` instead of `hass.states.async_set`
- [ ] Reference pattern: other HA camera integrations update entity state through the entity, not raw `async_set`

**Acceptance:** Motion ON in UI matches automation state; icon toggles correctly; no snap-back on coordinator refresh.

---

### 3. NVR wrong channel / duplicate sensors (NVR only)

**Files:** `custom_components/hikvision_isapi/binary_sensor.py` (~lines 87–93)

**Problem:** If Event/triggers has no match for a camera channel, code falls back to **first channel’s** trigger data. Multiple NVR channels can get wrong `channel_id` or duplicate `unique_id`s → missing/wrong sensors.

**Suggested fix:**

- [ ] Remove fallback to `list(supported_events_lookup[event_id].values())[0]`
- [ ] When no exact channel match: use `camera_id` from loop and `disabled=False` (same as else branch)
- [ ] Compare with NVR handling in other Hikvision HA integrations if needed

**Acceptance:** Each NVR channel gets distinct binary sensors mapped to correct channel.

**Note:** Not relevant for standalone IP cameras (single channel).

---

### 4. IO / alarm-input sensors never created

**Files:** `custom_components/hikvision_isapi/binary_sensor.py` (~line 130)

**Problem:** IO sensors only created when `has_io_inputs and supported_events` — i.e. `get_supported_events()` must succeed **and** return IO rows. If Event/triggers API fails (common on some firmware), no alarm-input entities even when `capabilities.input_ports > 0` → webhooks log “entity not found”.

**Suggested fix:**

- [ ] If `has_io_inputs` and `input_ports == N`, create `Alarm Input 1..N` from capabilities when Event/triggers failed or returned no IO rows
- [ ] Mirror fallback approach already used for video events when feature probe fails but event is in fallback list

**Acceptance:** Physical alarm inputs get entities even when Event/triggers API is unavailable.

**Note:** Only needed if using wired alarm inputs on the camera.

---

## P3 — Infrastructure / edge cases

### 8. Webhook blocking DNS

**Files:** `custom_components/hikvision_isapi/notifications.py` (`get_ip` → `socket.gethostbyname`)

**Problem:** Synchronous DNS on the HA event loop during webhook handling. Burst traffic can stall HA briefly.

**Suggested fix:**

- [ ] Resolve hostname via `await hass.async_add_executor_job(socket.gethostbyname, hostname)`
- [ ] Or cache host→IP at integration setup and refresh periodically

---

### 9. Reload race (`hass.data` popped too early)

**Files:** `custom_components/hikvision_isapi/__init__.py`, `notifications.py`

**Problem:** `async_unload_entry` pops `hass.data[DOMAIN][entry_id]` immediately after platform unload. In-flight webhooks can still arrive and fail looking up entry data.

**Suggested fix:**

- [ ] Pop `hass.data` only after platforms fully unloaded, or
- [ ] Set `domain_data["closing"] = True` before unload; webhook returns OK and ignores events when closing, or
- [ ] Keep minimal stub until no in-flight webhook handlers (harder)

---

### 10. Media player no teardown

**Files:** `custom_components/hikvision_isapi/media_player.py`

**Problem:** `async_media_stop()` only clears `_audio_session_id` locally. Does not cancel `_stream_audio` task or close camera two-way-audio TCP session. Unload mid-playback can wedge speaker path and compete with siren (403 audio busy).

**Suggested fix:**

- [ ] Store `_stream_task: asyncio.Task | None`
- [ ] Cancel task in `async_media_stop` and `async_will_remove_from_hass`
- [ ] Call API to close two-way audio socket / session if available

**Note:** Only relevant if using Speaker entity alongside siren.

---

### 11. Capability rescan → config reload mid-alarm

**Files:** `custom_components/hikvision_isapi/coordinator.py` (`_async_maybe_rescan_capabilities`)

**Problem:** Periodic feature re-scan can trigger `async_reload` on the config entry when capability profile changes. Worse combined with siren #1 — entities yanked mid-alarm.

**Suggested fix:**

- [ ] Before scheduling reload, check if any siren entity for entry has `is_on` → defer reload
- [ ] Or domain callback: stop all sirens before reload
- [ ] Log deferred reload reason

---

### 12. Webhook never unregistered

**Files:** `custom_components/hikvision_isapi/__init__.py`

**Problem:** Webhook registered once for first entry; not removed when last entry unloads.

**Suggested fix:**

- [ ] On `async_unload_entry`, if no remaining DOMAIN entries, unregister `EventNotificationsView`
- [ ] Re-register when first entry loads again

---

### 13. Single HA entry: webhook doesn’t verify source IP

**Files:** `custom_components/hikvision_isapi/notifications.py` (`get_isapi_device`)

**Problem:** When only one integration entry exists, any remote IP can POST to the webhook and trigger binary sensors.

**Suggested fix:**

- [ ] Always verify `request.remote` matches configured camera host IP (or MAC from alert XML) even for single entry
- [ ] Log and ignore mismatched sources

---

### 14. Binary sensors stuck ON (no inactive notification)

**Files:** `custom_components/hikvision_isapi/notifications.py`

**Problem:** If camera never sends `activeState=inactive`, motion stays ON until next inactive or manual clear. May be intentional edge-trigger behaviour.

**Suggested fix (optional):**

- [ ] Document as expected behaviour, or
- [ ] Add configurable auto-off timeout per event type

---

### 15. Uncommitted WIP (separate from above)

**Files:** `__init__.py`, `camera.py`, `device_helpers.py` (git status)

**Problem:** Local `configuration_url` work not committed.

**Suggested fix:**

- [ ] Review and commit when ready, or discard

---

## Recommended implementation order

1. **Siren hardening** — #1 + #5 (same PR)
2. **403 / reauth** — #6
3. **API lock** — #7
4. **Binary sensor entity path** — #2
5. **Webhook / unload hygiene** — #8, #9, #12, #13
6. **Media player teardown** — #10 (if speaker used)
7. **NVR / IO fallbacks** — #3, #4 (when needed)
8. **Capability reload guard** — #11

---

## Testing checklist (after fixes)

- [ ] Turn siren on via automation → turn off → no retriggers within 30s
- [ ] Turn siren on → reload integration → no retriggers after reload
- [ ] Turn siren on → call `turn_off` during slow `turn_on` → loop never starts
- [ ] Motion webhook → binary sensor state + icon both ON; coordinator refresh does not flip OFF incorrectly
- [ ] Trigger siren while coordinator polling → no reauth prompt
- [ ] (Optional) Play media on speaker → reload integration → siren still works

---

## Related context

- **Siren tone IDs differ per camera** (front door vs driveway) — automation must use label strings or per-entity tone IDs, not shared numeric IDs.
- **Camera has no siren stop API** — integration stops retriggers; last playing clip may finish (~few seconds).
- **HA log:** `home-assistant_2026-06-13T03-13-46.451Z.log` — alarm automation + `audioIsPlayingPleaseWait` 403s during overlapping siren calls.
