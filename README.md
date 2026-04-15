<div align="center">

# Hikvision ISAPI Controls

<img src="icon.png" alt="Hikvision ISAPI Controls Icon" width="128" height="128">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)

**Home Assistant integration for Hikvision cameras using ISAPI with comprehensive control options and real-time event detection.**

[Features](#features) • [Installation](#installation) • [Configuration](#configuration) • [Entities](#entities) • [Troubleshooting](#troubleshooting)

</div>

---

## Important Notes

> **Limited official support**: Tested mainly on the DS-2CD2387G3 (ColorVu G3). Other NVRs and standalone cameras may not have full support. Compatibility improves as issues are reported and PRs land.


### Known Issues

- **Binary sensors**: Motion is working. Other event types (intrusion, line crossing, etc.) usually need correct linkage and notification host on the camera.
- **Media player (Speaker)**: Playback is limited / unreliable for typical HA use (TTS and arbitrary MP3 are not really supported; see code notes on G.711 formats). The entity is also **disabled by default** in the entity registry for new setups.

---

## Features

### Automatic Discovery

- **DHCP Discovery**: Cameras are automatically discovered on your network via DHCP. Look for them in **Settings → Devices & Services → Discovered**.

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
| **Motion Target Type**        | Human, Vehicle, or Both |
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
| **Video Tampering Detection** | Enable/disable tamper detection          |
| **Alarm Input**               | Enable/disable alarm input port          |
| **Alarm Output**              | Control alarm output port (high/low)     |

### Other Features

- **Camera snapshots** – from any available stream
- **Firmware update** – diagnostic **Update** entity compares your firmware to the [community firmware archive](https://github.com/JoeyGE0/hikvision-fw-archive) (install is still manual on the device)
- **Audio alarm siren** – **Siren** entity when the camera exposes audio-alarm capabilities (tone, duration, volume)
- **Restart** – remote reboot
- **Test tone / trigger alarm** – diagnostic buttons when supported (often disabled by default in the registry)

---

## Installation

### Method 1: Manual Installation

1. Copy `hikvision_isapi` folder to `config/custom_components/`
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
- Update interval: 5-300 seconds (default: 30)

### Event Notifications Setup (Real-Time Events)

To enable real-time event detection, configure your camera to send events to Home Assistant:

#### Step 1: Configure Notification Host

The integration can automatically configure the notification host, or you can do it manually:

**Automatic (Recommended):**

- The integration will automatically set the notification host when you add it
- Uses webhook path: `/api/hikvision`

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

Friendly names start with your device name (e.g. `Garage`). **Entity IDs** are slugs derived by Home Assistant from those names (examples below use common patterns). Only entities whose features are detected on the device are created.

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
| `switch.{device_name}_alarm_input_1`             | Alarm input port 1 enable/disable        | Enabled        |
| `switch.{device_name}_alarm_output_1`            | Alarm output port 1 control (high/low)   | Enabled        |

### Binary sensor entities (real-time events)

Real-time event detection via webhook notifications. Motion detection is confirmed working!

| Entity ID                                              | Description                    | Device class | Status             |
| ------------------------------------------------------ | ------------------------------ | ------------ | ------------------ |
| `binary_sensor.{device_name}_motion`                   | Motion detection events        | `motion`     | ✅ Working         |
| `binary_sensor.{device_name}_intrusion`                | Intrusion detection events     | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_line_crossing`            | Line crossing events           | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_region_entrance`          | Region entrance events         | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_region_exiting`           | Region exiting events          | `motion`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_scene_change`             | Scene change events            | `tamper`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_video_loss`               | Video loss events              | `problem`    | ⚠️ Requires config |
| `binary_sensor.{device_name}_video_tampering`          | Video tampering events         | `tamper`     | ⚠️ Requires config |
| `binary_sensor.{device_name}_tamper_detection_enabled` | Tamper detection enabled state | `tamper`     | ✅ Working         |
| `binary_sensor.{device_name}_alarm_input_{port}`       | Alarm input events (I/O port)  | `motion`     | ⚠️ Requires config |

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
| `button.{device_name}_test_tone`       | Play test tone     | ⚠️ Partial; **disabled by default** in the registry |
| `button.{device_name}_trigger_alarm`   | Fire audio alarm once | When audio alarm is supported; **disabled by default** |

### Siren entities

| Entity ID (typical)           | Description | Notes |
| ----------------------------- | ----------- | ----- |
| `siren.{device_name}_alarm`   | Audio alarm | Only when the device reports audio-alarm / test-audio support |

### Update entities

| Entity ID (typical)                    | Description | Notes |
| -------------------------------------- | ----------- | ----- |
| `update.{device_name}_firmware_update` | Firmware vs archive | Diagnostic; **install from HA is not supported**—download and flash with Hikvision tools or the web UI |

### Media player entities

| Entity ID (typical)                  | Description    | Default / status |
| ------------------------------------ | -------------- | ---------------- |
| `media_player.{device_name}_speaker` | Speaker entity | **Disabled by default** in the registry; ❌ not suitable for normal TTS/MP3 playback |

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
| `region_id`        | integer | Region ID (if applicable)                     |

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
| `pydub`          | >=0.25.1 (optional, for audio) |

---

## Supported Models

| Model                         | Status   | Notes                                     |
| ----------------------------- | -------- | ----------------------------------------- |
| **DS-2CD2387G3 (ColorVu G3)** | Tested   | Core controls + motion events; other ISAPI events vary by firmware/config |
| Other Hikvision models        | Untested | May work depending on ISAPI compatibility |

---

## Troubleshooting

### Entities Not Showing

**Possible causes:**

- ISAPI not enabled on camera
- Incorrect credentials (username is case-sensitive, default is `admin`)
- User doesn't have "Remote: Parameters Settings" permission
- Network connectivity issues

**Solution:**

1. Check ISAPI is enabled in camera settings
2. Verify credentials (try `admin` in lowercase)
3. Check Home Assistant logs for errors
4. Enable debug logging:
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

**Status:** The speaker **media player** is not reliable for normal playback; prefer **Speaker volume** (number entity) for level control.

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
