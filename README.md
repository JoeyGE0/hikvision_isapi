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

> **Early Development**: This integration is in early development. There are likely bugs and it's only been tested on DS-2CD2387G3 (ColorVu G3). Other models haven't been tested.

> **Disclaimer**: mostly written with Cursor AI. I have no clue what I'm doing - help is appreciated 

### Known Issues

- **Binary Sensors**: Motion detection is working! Other event types (Intrusion, Line Crossing, etc.) may require proper configuration on the camera to work.
- **Media Player (Speaker)**: Media player functionality doesn't work properly (audio playback via TTS/MP3 is not functional).

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

**Note**: Motion detection is confirmed working. Other event types require proper camera configuration (see [Event Notifications Setup](#-event-notifications-setup-real-time-events)).

### Video/Image Controls

| Control                          | Options/Range                      |
| -------------------------------- | ---------------------------------- |
| **Day/Night Switch**             | Day, Night, or Auto mode           |
| **Day/Night Switch Sensitivity** | 0-7                                |
| **Day/Night Switch Delay**       | 5-120 seconds                      |
| **Supplement Light Mode**        | Smart, IR Supplement Light, or Off |
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
| **Motion Start Trigger Time** | 0-10000ms               |
| **Motion End Trigger Time**   | 0-10000ms               |

### Audio Controls

| Control               | Range/Options                                                     |
| --------------------- | ----------------------------------------------------------------- |
| **Speaker Volume**    | 0-100%                                                            |
| **Microphone Volume** | 0-100%                                                            |
| **Noise Reduction**   | Enable/disable                                                    |
| **Speaker**           | Media player for audio playback (TTS supported) - **NOT WORKING** |

### System Monitoring (Diagnostic)

| Metric                         | Description                                             |
| ------------------------------ | ------------------------------------------------------- |
| **CPU Utilization**            | Current CPU usage percentage (with aggregated graph)    |
| **Memory Usage**               | Current memory usage percentage (with aggregated graph) |
| **Device Uptime**              | Device uptime in hours/days                             |
| **Total Reboots**              | Total reboot count (disabled by default)                |
| **Active Streaming Sessions**  | Number of active video streams                          |
| **Streaming Clients**          | List of client IP addresses streaming                   |
| **Notification Host**          | Notification host IP address                            |
| **Notification Host Path**     | Notification host URL path                              |
| **Notification Host Port**     | Notification host port number                           |
| **Notification Host Protocol** | Notification host protocol (HTTP/HTTPS)                 |

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

- **Camera Snapshots** - Get snapshots from any available stream
- **Restart Button** - Remote camera restart
- **Test Tone Button** - Play test tone (partially working)

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
3. Add repository: `YOUR_GITHUB_USERNAME/hikvision-isapi-integration`
4. Category: Integration
5. Install and restart Home Assistant

## Branching tips

This repository currently uses `main` as the default branch. If you want a safer workflow, create a short‑lived feature branch (for example, `beta` or `fix/entity-events`) from `main`, push that branch, and open a pull request back to `main`. No big refactor is needed to start doing this—just branch, edit, and merge when you're ready. If you keep working directly on `main`, commit regularly so you can roll back easily if something breaks.

---

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

All entities are prefixed with your device name (e.g., `Garage`).

### Select Entities

| Entity ID                                       | Description                                 | Default Status |
| ----------------------------------------------- | ------------------------------------------- | -------------- |
| `select.{device_name}_day_night_switch`         | Day/Night/Auto mode                         | Enabled        |
| `select.{device_name}_supplement_light`         | Supplement light mode                       | Enabled        |
| `select.{device_name}_light_brightness_control` | Light brightness control mode (Auto/Manual) | Disabled       |
| `select.{device_name}_motion_target_type`       | Motion detection target type                | Enabled        |

### Number Entities

| Entity ID                                           | Description                  | Range     | Default Status |
| --------------------------------------------------- | ---------------------------- | --------- | -------------- |
| `number.{device_name}_day_night_switch_sensitivity` | IR sensitivity               | 0-7       | Enabled        |
| `number.{device_name}_day_night_switch_delay`       | IR filter delay              | 5-120s    | Enabled        |
| `number.{device_name}_speaker_volume`               | Speaker volume               | 0-100%    | Enabled        |
| `number.{device_name}_microphone_volume`            | Microphone volume            | 0-100%    | Enabled        |
| `number.{device_name}_led_on_duration`              | LED duration                 | 10-300s   | Enabled        |
| `number.{device_name}_white_light_brightness`       | White light brightness       | 0-100%    | Enabled        |
| `number.{device_name}_ir_light_brightness`          | IR light brightness          | 0-100%    | Enabled        |
| `number.{device_name}_white_light_brightness_limit` | White light brightness limit | 0-100%    | Enabled        |
| `number.{device_name}_ir_light_brightness_limit`    | IR light brightness limit    | 0-100%    | Enabled        |
| `number.{device_name}_motion_sensitivity`           | Motion sensitivity           | 0-100%    | Enabled        |
| `number.{device_name}_motion_start_trigger_time`    | Motion start time            | 0-10000ms | Enabled        |
| `number.{device_name}_motion_end_trigger_time`      | Motion end time              | 0-10000ms | Disabled       |

### Switch Entities

| Entity ID                                        | Description                              | Default Status |
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

### Binary Sensor Entities (Real-Time Events)

Real-time event detection via webhook notifications. Motion detection is confirmed working!

| Entity ID                                              | Description                    | Device Class | Status             |
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

### Sensor Entities (Diagnostic)

| Entity ID                                         | Description                  | Unit         | Default Status |
| ------------------------------------------------- | ---------------------------- | ------------ | -------------- |
| `sensor.{device_name}_cpu_utilization`            | CPU usage                    | %            | Enabled        |
| `sensor.{device_name}_memory_usage`               | Memory usage                 | %            | Enabled        |
| `sensor.{device_name}_device_uptime`              | Device uptime                | hours/days   | Enabled        |
| `sensor.{device_name}_total_reboots`              | Total reboot count           | count        | Disabled       |
| `sensor.{device_name}_active_streaming_sessions`  | Active stream count          | count        | Enabled        |
| `sensor.{device_name}_streaming_clients`          | Streaming client IPs         | IP addresses | Enabled        |
| `sensor.{device_name}_notification_host`          | Notification host IP address | -            | Enabled        |
| `sensor.{device_name}_notification_host_path`     | Notification host URL path   | -            | Enabled        |
| `sensor.{device_name}_notification_host_port`     | Notification host port       | -            | Enabled        |
| `sensor.{device_name}_notification_host_protocol` | Notification host protocol   | -            | Enabled        |

**Note**: CPU and Memory sensors display aggregated graphs with smoothed data visualization (similar to Home Assistant's system monitor).

### Camera Entities

| Entity ID                                | Description                      | Status       |
| ---------------------------------------- | -------------------------------- | ------------ |
| `camera.{device_name}_main`              | Main Stream (high quality)       | ✅ Working   |
| `camera.{device_name}_sub_stream`        | Sub-stream (lower quality)       | ✅ Working\* |
| `camera.{device_name}_third_stream`      | Third Stream (if available)      | ✅ Working\* |
| `camera.{device_name}_transcoded_stream` | Transcoded Stream (if available) | ✅ Working\* |

\* Disabled by default - enable in entity registry if needed

**Note**: If your camera doesn't support multiple streams, you'll see a single `camera.{device_name}_snapshot` entity instead.

### Button Entities

| Entity ID                        | Description    | Status               |
| -------------------------------- | -------------- | -------------------- |
| `button.{device_name}_restart`   | Restart camera | ✅ Working           |
| `button.{device_name}_test_tone` | Play test tone | ⚠️ Partially Working |

### Media Player Entities

| Entity ID                            | Description    | Status         |
| ------------------------------------ | -------------- | -------------- |
| `media_player.{device_name}_speaker` | Audio playback | ❌ Not Working |

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
| `requests`       | Latest                         |
| `pydub`          | >=0.25.1 (optional, for audio) |

---

## Supported Models

| Model                         | Status   | Notes                                     |
| ----------------------------- | -------- | ----------------------------------------- |
| **DS-2CD2387G3 (ColorVu G3)** | Tested   | Fully working (except binary sensors)     |
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

1. Configure event notifications (see [Event Notifications Setup](#-event-notifications-setup-real-time-events))
2. Ensure webhook URL is correct: `http://YOUR_HA_IP:8123/api/hikvision`
3. Verify "Notify Surveillance Center" is enabled for each event type you want
4. Check Home Assistant logs for event type received (enable debug logging)
5. Verify the event type is supported (check logs for "Unsupported event type" messages)

### Audio Not Working

**Status:** Media player functionality is currently not working properly.

**Workaround:** Use speaker volume control instead.

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

---

<div align="center">

**Made with Cursor AI**

[Back to Top](#hikvision-isapi-controls)

</div>
