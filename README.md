<div align="center">

# Hikvision ISAPI Controls

<img src="https://brands.home-assistant.io/hikvision/icon.png" alt="Hikvision ISAPI Controls Icon" width="128" height="128">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)

**Home Assistant integration for Hikvision cameras using ISAPI with comprehensive control options and real-time event detection.**

[Features](#features) • [Installation](#installation) • [Configuration](#configuration) • [Entities](#entities) • [Troubleshooting](#troubleshooting)

</div>

---

## Important Notes

> **Limited official support**: Tested mainly on the DS-2CD2387G3 (ColorVu G3) and DS-2CD1383G2. Standalone cameras and NVRs are supported when ISAPI exposes the relevant endpoints; feature coverage varies by model and firmware. Compatibility improves as issues are reported and PRs land.

### Known Issues

- **Binary sensors**: Motion is working. Other event types (intrusion, line crossing, etc.) usually need correct linkage and notification host on the camera. Event binary sensors are **disabled by default** when the camera reports the trigger as disabled in `Event/triggers`.
- **Media player (Speaker)**: Only created when two-way audio is detected. Playback is limited / unreliable for typical HA use (TTS and arbitrary MP3 are not really supported; see code notes on G.711 formats). The entity is also **disabled by default** in the entity registry for new setups.

---

## Features

### Automatic Discovery

- **DHCP Discovery**: Cameras are automatically discovered on your network via DHCP (Hikvision MAC OUIs). Look for them in **Settings → Devices & Services → Discovered**.

### Capability-Based Entities

- **Feature detection**: On setup, the integration probes ISAPI endpoints and only creates entities the device actually supports.
- **Periodic rescan**: Capabilities are re-checked about 15 minutes after startup, then every 6 hours; if the feature set changes, the config entry reloads so entities stay in sync.

### NVR Support

- **Multi-channel**: NVRs expose one device per channel with `via_device` linking back to the NVR.
- **Proxied cameras**: RTSP snapshots and streams use the NVR proxy path when channels are proxied.

### Real-Time Event Detection

Real-time event detection via webhook notifications. Binary sensors update instantly when events occur.

| Feature                       | Description                        |
| ----------------------------- | ---------------------------------- |
| **Motion Detection**          | Real-time motion events (working!) |
| **Intrusion Detection**       | Field detection events             |
| **Line Crossing Detection**   | Line crossing events               |
| **Region Entrance/Exiting**   | Region-based detection events      |
| **Scene Change Detection**    | Scene change events                |
| **Video Loss Detection**      | Video loss events                  |
| **Video Tampering Detection** | Tamper detection events            |
| **Defocus Detection**         | Defocus / out-of-focus events      |

**Note**: Motion detection is confirmed working. Other event types require proper camera configuration (see [Event Notifications Setup](#event-notifications-setup-real-time-events)).

### Video/Image Controls

| Control                          | Options/Range                      |
| -------------------------------- | ---------------------------------- |
| **Day/Night Switch**             | Day, Night, or Auto mode           |
| **Day/Night Switch Sensitivity** | 0-7                                |
| **Day/Night Switch Delay**       | 5-120 seconds                      |
| **Supplement Light Mode**        | Smart, White Supplement Light, IR Supplement Light, or Off |
| **Light Brightness Control**     | Auto or Manual mode                |
| **White Light Brightness**       | 0-100%                             |
| **IR Light Brightness**          | 0-100%                             |
| **White Light Brightness Limit** | 0-100%                             |
| **IR Light Brightness Limit**    | 0-100%                             |
| **LED On Duration**              | 10-300 seconds                     |

### Motion Detection Settings

| Setting                       | Options/Range           |
| ----------------------------- | ----------------------- |
| **Motion Sensitivity**        | 0-100%                  |
| **Motion Target Type**        | `human`, `vehicle`, or `human,vehicle` |
| **Motion Start Trigger Time** | 0–10000 ms (100 ms steps) |
| **Motion End Trigger Time**   | 0–10000 ms (100 ms steps) |

### Audio Controls

| Control               | Range/Options                                                     |
| --------------------- | ----------------------------------------------------------------- |
| **Speaker Volume**    | 0-100%                                                            |
| **Microphone Volume** | 0-100%                                                            |
| **Noise Reduction**   | Enable/disable                                                    |
| **Speaker**           | Media player entity (experimental; **disabled by default**; not suitable for normal TTS/MP3) |

### System Monitoring (Diagnostic)

| Metric                         | Description                                             |
| ------------------------------ | ------------------------------------------------------- |
| **CPU Utilization**            | Current CPU usage percentage (with aggregated graph)    |
| **Memory Usage**               | Current memory usage percentage (with aggregated graph) |
| **Device Uptime**              | Device uptime in hours/days                             |
| **Total Reboots**              | Total reboot count (disabled by default)                |
| **Active Streaming Sessions**  | Number of active video streams                          |
| **Streaming Clients**          | List of client IP addresses streaming                   |
| **Notifications Host**          | Surveillance / HTTP notification host IP                 |
| **Notifications Host Path**     | URL path on the notification host                      |
| **Notifications Host Port**     | Port on the notification host                         |
| **Notifications Host Protocol** | Protocol (HTTP/HTTPS)                                  |

### Camera Streams

Multiple camera stream support with separate entities for each stream type:

| Stream Type           | Description                            | Default Status |
| --------------------- | -------------------------------------- | -------------- |
| **Main Stream**       | Primary high-quality video stream      | Enabled        |
| **Sub-stream**        | Lower quality stream for preview       | Disabled       |
| **Third Stream**      | Additional stream (if available)       | Disabled       |
| **Transcoded Stream** | Transcoded video stream (if available) | Disabled       |

All streams support RTSP streaming and snapshots. Only streams available on your camera will be created.

### Detection Controls

| Control                       | Description                              |
| ----------------------------- | ---------------------------------------- |
| **Motion Detection**          | Enable/disable motion detection          |
| **Intrusion Detection**       | Enable/disable intrusion detection       |
| **Line Crossing Detection**   | Enable/disable line crossing detection   |
| **Scene Change Detection**    | Enable/disable scene change detection    |
| **Region Entrance Detection** | Enable/disable region entrance detection |
| **Region Exiting Detection**  | Enable/disable region exiting detection  |
| **Defocus Detection**         | Enable/disable defocus detection         |
| **Video Tampering Detection** | Enable/disable tamper detection          |
| **Alarm Input**               | Enable/disable alarm input port          |
| **Alarm Output**              | Control alarm output port (high/low)     |

### Other Features

- **Camera snapshots** – from any available stream
- **Firmware update** – diagnostic **Update** entity compares your firmware to the [community firmware archive](https://github.com/JoeyGE0/hikvision-fw-archive) and can **install from Home Assistant** when the archive provides a download URL for your model
- **Audio alarm siren** – **Siren** entity when the camera exposes audio-alarm / test-audio support (tone, duration, volume, retrigger loop)
- **Restart** – remote reboot
- **Trigger alarm** – diagnostic button when supported (disabled by default in the registry)

---

## Installation

### Method 1: Manual Installation

1. Copy the `custom_components/hikvision_isapi` directory from this repository into your Home Assistant `config/custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **"Hikvision ISAPI Controls"**
5. Enter camera IP, username (default: `admin`), password, and update interval (default: 30 seconds)

**OR** if your camera is discovered via DHCP:

- Look in **Settings → Devices & Services → Discovered** for your Hikvision camera
- Click **Configure** and enter your credentials

### Method 2: HACS (Custom Repository)

1. Open HACS → Integrations
2. Click the three dots (⋮) → Custom repositories
3. Add repository: `JoeyGE0/hikvision_isapi`
4. Category: Integration
5. Install and restart Home Assistant

## Configuration

### Camera Setup Requirements

- ISAPI must be enabled on your camera
- User needs **Remote: Parameters Settings** permission
- Update interval: 5–300 seconds (default: 30)

### Advanced Options (config flow)

| Option | Default | Description |
| ------ | ------- | ----------- |
| **Verify SSL certificate** | On | Turn off for cameras that only speak HTTP |
| **Configure notification host on camera** | On | Writes your HA URL and `/api/hikvision` path to the camera |
| **Notification host URL** | Auto (HA LAN IP) | Override when HA is behind NAT or you use a reverse proxy |
| **Forced RTSP port** | Empty | Set if RTSP is not on the default port |

Reconfigure the integration anytime from **Settings → Devices & Services → Hikvision ISAPI Controls → Configure**.

### Event Notifications Setup (Real-Time Events)

To enable real-time event detection, configure your camera to send events to Home Assistant:

#### Step 1: Configure Notification Host

The integration can automatically configure the notification host, or you can do it manually:

**Automatic (Recommended):**

- Enabled by default via **Configure notification host on camera**
- Sets protocol, IP, port, and path (`/api/hikvision`) on the camera
- Attempts to enable **Notify Surveillance Center** on supported event triggers

**Manual Configuration:**

1. In your camera's web interface, go to **Configuration → Event → Notification**
2. Add a new HTTP notification host:
   - **Protocol**: `HTTP`
   - **IP Address**: Your Home Assistant IP address
   - **Port**: `8123` (or your HA port)
   - **URL**: `/api/hikvision`

#### Step 2: Enable Event Notifications

For each event type you want (Motion, Intrusion, etc.):

1. Go to **Event → Linkage Action**
2. Enable **Notify Surveillance Center**
3. Select the notification host you created

Once configured, binary sensors will update in real-time when events occur.

**Note**: Motion detection is confirmed working. Other event types should work if properly configured on the camera. Check the logs if events aren't being received.

---

## Entities

Friendly names start with your device name (e.g. `Garage Motion`). **Entity IDs** are built from a slug of the device name plus the ISAPI event or setting key (examples below use common patterns). Only entities whose features are detected on the device are created.

### Select entities

| Entity ID (typical)                             | Description                                 | Default status |
| ----------------------------------------------- | ------------------------------------------- | -------------- |
| `select.{device_name}_day_night_switch`         | Day / Night / Auto                          | Enabled        |
| `select.{device_name}_supplement_light`         | Supplement light mode                       | Enabled        |
| `select.{device_name}_light_brightness_control` | Light brightness Auto / Manual              | Disabled       |
| `select.{device_name}_motion_target_type`       | Motion target: `human`, `vehicle`, or both (`human,vehicle`) | Enabled        |
| `select.{device_name}_audio_type`               | Audio alarm class (from device capabilities) | Disabled\*     |
| `select.{device_name}_warning_sound`            | Warning sound (from device capabilities)    | Disabled\*     |

\*Created only when the camera reports audio-alarm capabilities.

### Number entities

| Entity ID (typical)                                 | Description                  | Range     | Default status |
| --------------------------------------------------- | ---------------------------- | --------- | -------------- |
| `number.{device_name}_day_night_switch_sensitivity` | Day/Night IR sensitivity     | 0–7       | Enabled        |
| `number.{device_name}_day_night_switch_delay`       | Day/Night IR filter delay    | 5–120 s   | Enabled        |
| `number.{device_name}_speaker_volume`               | Two-way / speaker volume     | 0–100%    | Enabled        |
| `number.{device_name}_microphone_volume`            | Microphone volume            | 0–100%    | Enabled        |
| `number.{device_name}_led_on_duration`              | White-light LED on duration  | 10–300 s  | Enabled        |
| `number.{device_name}_white_light_brightness`       | White light brightness       | 0–100%    | Disabled       |
| `number.{device_name}_ir_light_brightness`          | IR light brightness          | 0–100%    | Disabled       |
| `number.{device_name}_white_light_brightness_limit` | White light brightness cap   | 0–100%    | Disabled       |
| `number.{device_name}_ir_light_brightness_limit`    | IR light brightness cap      | 0–100%    | Disabled       |
| `number.{device_name}_motion_sensitivity`           | Motion sensitivity           | 0–100%    | Enabled        |
| `number.{device_name}_motion_start_trigger_time`    | Motion start trigger         | 0–10000 ms (100 ms steps) | Enabled        |
| `number.{device_name}_motion_end_trigger_time`      | Motion end trigger           | 0–10000 ms (100 ms steps) | Disabled       |
| `number.{device_name}_brightness`                   | Image brightness             | 0–100%    | Disabled       |
| `number.{device_name}_contrast`                     | Image contrast               | 0–100%    | Disabled       |
| `number.{device_name}_saturation`                   | Image saturation             | 0–100%    | Disabled       |
| `number.{device_name}_sharpness`                    | Image sharpness              | 0–100%    | Disabled       |
| `number.{device_name}_alarm_times`                  | Audio alarm repeat count     | 1–50      | Disabled\*     |
| `number.{device_name}_alarm_output_volume`          | Audio alarm output volume (not media speaker) | 1–100% | Disabled\*     |

\*Created when audio-alarm features are detected on the device.

### Switch entities

| Entity ID                                        | Description                              | Default status |
| ------------------------------------------------ | ---------------------------------------- | -------------- |
| `switch.{device_name}_noise_reduction`           | Noise reduction on/off                   | Enabled        |
| `switch.{device_name}_motion_detection`          | Motion detection enable/disable          | Enabled        |
| `switch.{device_name}_video_tampering_detection` | Video tampering detection enable/disable | Enabled        |
| `switch.{device_name}_intrusion_detection`       | Intrusion detection enable/disable       | Enabled        |
| `switch.{device_name}_line_crossing_detection`   | Line crossing detection enable/disable   | Enabled        |
| `switch.{device_name}_scene_change_detection`    | Scene change detection enable/disable    | Enabled        |
| `switch.{device_name}_region_entrance_detection` | Region entrance detection enable/disable | Enabled        |
| `switch.{device_name}_region_exiting_detection`  | Region exiting detection enable/disable  | Enabled        |
| `switch.{device_name}_defocus_detection`         | Defocus detection enable/disable         | Enabled        |
| `switch.{device_name}_alarm_input_1`             | Alarm input port 1 enable/disable in camera config | Enabled        |
| `switch.{device_name}_alarm_output_1`            | Alarm output relay high/low (external siren)       | Enabled        |

### Binary sensor entities (real-time events)

Real-time event detection via webhook notifications. Motion detection is confirmed working!

| Entity ID (typical)                                      | Description                    | Device class | Status             |
| -------------------------------------------------------- | ------------------------------ | ------------ | ------------------ |
| `binary_sensor.{device_slug}_motiondetection`            | Motion detection events        | `motion`     | ✅ Working         |
| `binary_sensor.{device_slug}_fielddetection`             | Intrusion detection events     | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_linedetection`              | Line crossing events           | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_regionentrance`             | Region entrance events         | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_regionexiting`              | Region exiting events          | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_scenechangedetection`       | Scene change events            | `tamper`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_videoloss`                  | Video loss events              | `problem`    | ⚠️ Requires config |
| `binary_sensor.{device_slug}_tamperdetection`            | Video tampering events         | `tamper`     | ⚠️ Requires config |
| `binary_sensor.{device_slug}_defocus`                    | Defocus events                 | `problem`    | ⚠️ Requires config |
| `binary_sensor.{device_slug}_{port}_io`                    | Alarm input events (I/O port)  | —            | ⚠️ Requires config |

**Note:** `{device_slug}` is a lowercase slug of the device name. Binary sensors are **disabled by default** when the camera marks the matching trigger as disabled in `Event/triggers`.

### Sensor entities (diagnostic)

| Entity ID (typical)                                | Description                  | Unit         | Default status |
| ------------------------------------------------- | ---------------------------- | ------------ | -------------- |
| `sensor.{device_name}_cpu_utilization`            | CPU usage                    | %            | Enabled        |
| `sensor.{device_name}_memory_usage`               | Memory usage                 | %            | Enabled        |
| `sensor.{device_name}_device_uptime`              | Device uptime                | hours/days   | Enabled        |
| `sensor.{device_name}_total_reboots`              | Total reboot count           | count        | Disabled       |
| `sensor.{device_name}_active_streaming_sessions`  | Active stream count          | count        | Enabled        |
| `sensor.{device_name}_streaming_clients`          | Streaming client IPs         | IP addresses | Enabled        |
| `sensor.{device_name}_notifications_host`         | Notifications host IP        | —            | Enabled        |
| `sensor.{device_name}_notifications_host_path`    | Notifications host URL path  | —            | Enabled        |
| `sensor.{device_name}_notifications_host_port`    | Notifications host port      | —            | Enabled        |
| `sensor.{device_name}_notifications_host_protocol` | Notifications host protocol | —            | Enabled        |

**Note**: CPU and Memory sensors display aggregated graphs with smoothed data visualization (similar to Home Assistant's system monitor).

### Camera entities

| Entity ID                                | Description                      | Status       |
| ---------------------------------------- | -------------------------------- | ------------ |
| `camera.{device_name}_main`              | Main Stream (high quality)       | ✅ Working   |
| `camera.{device_name}_sub_stream`        | Sub-stream (lower quality)       | ✅ Working\* |
| `camera.{device_name}_third_stream`      | Third Stream (if available)      | ✅ Working\* |
| `camera.{device_name}_transcoded_stream` | Transcoded Stream (if available) | ✅ Working\* |

\* Disabled by default - enable in entity registry if needed

**Note**: If your camera doesn't support multiple streams, you'll see a single `camera.{device_name}_snapshot` entity instead.

### Button entities

| Entity ID (typical)                    | Description        | Notes |
| -------------------------------------- | ------------------ | ----- |
| `button.{device_name}_restart`         | Restart camera     | ✅    |
| `button.{device_name}_trigger_alarm`   | Fire audio alarm once | When `test_audio_alarm` is detected; **disabled by default** |

### Manual command reference (audio alarm trigger)

If someone wants to implement alarm triggering outside Home Assistant, these are the ISAPI calls used:

1. Read current alarm config (gets selected sound ID):

   `GET /ISAPI/Event/triggers/notifications/AudioAlarm?format=json`

2. Trigger the selected sound once:

   `PUT /ISAPI/Event/triggers/notifications/AudioAlarm/{audioID}/test?format=json`

Authentication is Hikvision Digest auth. Most cameras accept an empty JSON body (`{}`) on the trigger call.

Example using curl:

```bash
# Read current config and note AudioAlarm.audioID
curl --digest -u 'admin:YOUR_PASSWORD' \
  'http://CAMERA_IP/ISAPI/Event/triggers/notifications/AudioAlarm?format=json'

# Trigger one playback for audioID 14
curl --digest -u 'admin:YOUR_PASSWORD' \
  -X PUT \
  -H 'Content-Type: application/json' \
  -d '{}' \
  'http://CAMERA_IP/ISAPI/Event/triggers/notifications/AudioAlarm/14/test?format=json'
```

Common responses:

- `200`: trigger accepted
- `403`: unsupported, busy, or insufficient permissions
- `404`: endpoint or `audioID` not available on that model/firmware

### Siren entities

| Entity ID (typical)           | Description | Notes |
| ----------------------------- | ----------- | ----- |
| `siren.{device_name}_alarm`   | Audio alarm | When `test_audio_alarm` is detected; supports tone, duration, volume, and retrigger loop |

### Update entities

| Entity ID (typical)                    | Description | Notes |
| -------------------------------------- | ----------- | ----- |
| `update.{device_name}_firmware_update` | Firmware vs archive | Diagnostic; **Install** appears when the archive has a download URL for your model—uploads via ISAPI, polls upgrade status, and waits for reboot. Use with care. |

### Media player entities

| Entity ID (typical)                  | Description    | Default / status |
| ------------------------------------ | -------------- | ---------------- |
| `media_player.{device_name}_speaker` | Speaker entity | Only when two-way audio is detected; **disabled by default**; ❌ not suitable for normal TTS/MP3 playback |

---

## Home Assistant Events

When camera events occur, the integration fires `hikvision_isapi_event` events with the following data:

| Field              | Type    | Description                                   |
| ------------------ | ------- | --------------------------------------------- |
| `channel_id`       | integer | Camera channel ID                             |
| `io_port_id`       | integer | I/O port ID (for alarm input/output events)   |
| `camera_name`      | string  | Camera name                                   |
| `event_id`         | string  | Event type (motiondetection, intrusion, etc.) |
| `detection_target` | string  | Detection target (if applicable)              |
| `region_id`        | integer | Region ID (present when `detection_target` is set) |

### Example Automation

```yaml
automation:
  - alias: "Motion Detected"
    description: "Notify when motion is detected"
    trigger:
      platform: event
      event_type: hikvision_isapi_event
      event_data:
        event_id: motiondetection
    action:
      - service: notify.mobile_app
        data:
          title: "Motion Detected"
          message: "Motion detected on {{ trigger.event.data.camera_name }}"
          data:
            actions:
              - action: "view_camera"
                title: "View Camera"
```

---

## Requirements

| Requirement      | Version                        |
| ---------------- | ------------------------------ |
| Home Assistant   | 2023.1+                        |
| Python           | 3.10+                          |
| Hikvision Camera | ISAPI enabled                  |
| `requests`       | Installed with the integration (`manifest.json`) |
| `aiohttp`        | Installed with the integration (`manifest.json`) |
| `pydub`          | >=0.25.1 (installed with the integration; used for audio conversion in the media player) |

---

## Supported Models

| Model                         | Status   | Notes                                     |
| ----------------------------- | -------- | ----------------------------------------- |
| **DS-2CD2387G3 (ColorVu G3)** | Tested   | Core controls + motion events; other ISAPI events vary by firmware/config |
| Hikvision NVRs                | Supported | Multi-channel; proxied RTSP; feature set depends on connected cameras |
| Other Hikvision models        | Untested | May work depending on ISAPI compatibility |

---

## Troubleshooting

### Entities Not Showing

**Possible causes:**

- ISAPI not enabled on camera
- Incorrect credentials (username is case-sensitive, default is `admin`)
- User doesn't have "Remote: Parameters Settings" permission
- Network connectivity issues
- Feature not exposed on this model/firmware (entities are created only after endpoint probing succeeds)

**Solution:**

1. Check ISAPI is enabled in camera settings
2. Verify credentials (try `admin` in lowercase)
3. Check Home Assistant logs for errors
4. Download **Diagnostics** from **Settings → Devices & Services → Hikvision ISAPI Controls → ⋮ → Download diagnostics** to see which features were detected
5. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.hikvision_isapi: debug
   ```

### DHCP Discovery Not Working

**Possible causes:**

- Camera not on same network
- Camera already configured
- MAC address not in discovery list

**Solution:**

1. Ensure camera is on the same network as Home Assistant
2. Restart the camera to trigger a new DHCP request
3. Check **Settings → Devices & Services → Discovered** for the camera
4. If camera is already configured, it won't appear in discovered devices

### Event Binary Sensors Not Working

**Status**: Motion detection is working! Other events may require proper camera configuration.

**Possible causes:**

- Event notifications not configured on camera
- "Notify Surveillance Center" not enabled in Linkage Action
- Incorrect webhook URL
- Event type not supported by camera

**Solution:**

1. Configure event notifications (see [Event Notifications Setup](#event-notifications-setup-real-time-events))
2. Ensure webhook URL is correct: `http://YOUR_HA_IP:8123/api/hikvision`
3. Verify "Notify Surveillance Center" is enabled for each event type you want
4. Check Home Assistant logs for event type received (enable debug logging)
5. Verify the event type is supported (check logs for "Unsupported event type" messages)

### Audio / media player

**Status:** The speaker **media player** is only added when two-way audio is detected and is not reliable for normal playback; prefer **Speaker volume** (number entity) for level control.

**Tip:** Enable the media player in the entity registry if you removed it or started from a template that hides it.

### Camera Streams Not Showing

**Possible causes:**

- Camera doesn't support multiple streams
- Stream detection failed during setup

**Solution:**

1. Check Home Assistant logs for stream detection errors
2. If only one camera entity shows, your camera may only support one stream
3. Enable debug logging to see which streams were detected:
   ```yaml
   logger:
     logs:
       custom_components.hikvision_isapi: debug
   ```
4. Check that your camera model supports multiple streams

### Firmware Update

**Install from Home Assistant** is available when the [firmware archive](https://github.com/JoeyGE0/hikvision-fw-archive) lists a matching package with a download URL. The integration downloads the file, uploads it over ISAPI, polls `upgradeStatus`, and waits for the camera to reboot.

**If Install is missing or fails:**

- Your model may not be in the archive yet, or no HTTP download URL is available
- Confirm **Remote: Parameters Settings** and upgrade permissions on the camera user
- Check logs during install—the upload connection may drop while the camera flashes firmware (this can be normal)
- Prefer a wired connection; do not power-cycle during upgrade
- It does work but proceed with caution!!!!

---

## Reporting Issues

When reporting issues, please include:

- **Camera model and firmware version**
- **Home Assistant version**
- **Logs** (enable debug: `logger: logs: custom_components.hikvision_isapi: debug`)
- **Steps to reproduce the issue**
- **Screenshots** (if applicable)

---

## License

This project is licensed under the **MIT License**.

---

## Credits

This integration was partially inspired by the [hikvision_next](https://github.com/maciej-or/hikvision_next) integration by [@maciej-or](https://github.com/maciej-or).

Workflow improvements assisted by Cursor AI.

---

<div align="center">

[Back to Top](#hikvision-isapi-controls)

</div>
