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

> **Disclaimer**: All written by Cursor AI. I have no clue what I'm doing.

### Known Issues

- **Binary Sensors (Motion, Intrusion, etc.)**: Event detection binary sensors are currently not working properly. They may not update when events occur.
- **Media Player (Speaker)**: Media player functionality doesn't work properly (audio playback via TTS/MP3 is not functional).

---

## Features

### Automatic Discovery

- **DHCP Discovery**: Cameras are automatically discovered on your network via DHCP. Look for them in **Settings → Devices & Services → Discovered**.

### Real-Time Event Detection

Real-time event detection via webhook notifications. Binary sensors update instantly when events occur.

| Feature                       | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| **Motion Detection**          | Real-time motion events (not just enabled/disabled state) |
| **Intrusion Detection**       | Field detection events                                    |
| **Line Crossing Detection**   | Line crossing events                                      |
| **Region Entrance/Exiting**   | Region-based detection events                             |
| **Scene Change Detection**    | Scene change events                                       |
| **Video Loss Detection**      | Video loss events                                         |
| **Video Tampering Detection** | Tamper detection events                                   |

### Video/Image Controls

| Control                          | Options/Range                      |
| -------------------------------- | ---------------------------------- |
| **Day/Night Switch**             | Day, Night, or Auto mode           |
| **Day/Night Switch Sensitivity** | 0-7                                |
| **Day/Night Switch Delay**       | 5-120 seconds                      |
| **Supplement Light Mode**        | Smart, IR Supplement Light, or Off |
| **White Light Brightness**       | 0-100%                             |
| **IR Light Brightness**          | 0-100%                             |
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

| Metric                        | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| **CPU Utilization**           | Current CPU usage percentage (with aggregated graph)    |
| **Memory Usage**              | Current memory usage percentage (with aggregated graph) |
| **Device Uptime**             | Device uptime in hours/days                             |
| **Total Reboots**             | Total reboot count                                      |
| **Active Streaming Sessions** | Number of active video streams                          |
| **Streaming Clients**         | List of client IP addresses streaming                   |

### Other Features

- **Snapshot Camera** - Get camera snapshots
- **Restart Button** - Remote camera restart
- **Tamper Detection Enabled** - Configuration state

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

---

## Configuration

### Camera Setup Requirements

- ISAPI must be enabled on your camera
- User needs **Remote: Parameters Settings** permission
- Update interval: 5-300 seconds (default: 30)

### Event Notifications Setup (Real-Time Events)

To enable real-time event detection, configure your camera to send events to Home Assistant:

#### Step 1: Configure Notification Host

1. In your camera's web interface, go to **Configuration → Event → Notification**
2. Add a new HTTP notification host:
   - **Protocol**: `HTTP`
   - **IP Address**: Your Home Assistant IP address
   - **Port**: `8123` (or your HA port)
   - **URL**: `/api/hikvision_isapi`

#### Step 2: Enable Event Notifications

For each event type you want (Motion, Intrusion, etc.):

1. Go to **Event → Linkage Action**
2. Enable **Notify Surveillance Center**
3. Select the notification host you created

Once configured, binary sensors will update in real-time when events occur.

**Note**: Binary sensors are currently experiencing issues and may not update properly even when configured correctly.

---

## Entities

All entities are prefixed with your device name (e.g., `Garage`).

### Select Entities

| Entity ID                                 | Description                  |
| ----------------------------------------- | ---------------------------- |
| `select.{device_name}_day_night_switch`   | Day/Night/Auto mode          |
| `select.{device_name}_supplement_light`   | Supplement light mode        |
| `select.{device_name}_motion_target_type` | Motion detection target type |

### Number Entities

| Entity ID                                           | Description            | Range     |
| --------------------------------------------------- | ---------------------- | --------- |
| `number.{device_name}_day_night_switch_sensitivity` | IR sensitivity         | 0-7       |
| `number.{device_name}_day_night_switch_delay`       | IR filter delay        | 5-120s    |
| `number.{device_name}_speaker_volume`               | Speaker volume         | 0-100%    |
| `number.{device_name}_microphone_volume`            | Microphone volume      | 0-100%    |
| `number.{device_name}_led_on_duration`              | LED duration           | 10-300s   |
| `number.{device_name}_white_light_brightness`       | White light brightness | 0-100%    |
| `number.{device_name}_ir_light_brightness`          | IR light brightness    | 0-100%    |
| `number.{device_name}_motion_sensitivity`           | Motion sensitivity     | 0-100%    |
| `number.{device_name}_motion_start_trigger_time`    | Motion start time      | 0-10000ms |
| `number.{device_name}_motion_end_trigger_time`      | Motion end time        | 0-10000ms |

### Switch Entities

| Entity ID                              | Description            |
| -------------------------------------- | ---------------------- |
| `switch.{device_name}_noise_reduction` | Noise reduction on/off |

### Binary Sensor Entities (Real-Time Events)

**⚠️ Currently Not Working**: These sensors are experiencing issues and may not update when events occur.

| Entity ID                                              | Description                    | Device Class |
| ------------------------------------------------------ | ------------------------------ | ------------ |
| `binary_sensor.{device_name}_motion`                   | Motion detection events        | `motion`     |
| `binary_sensor.{device_name}_intrusion`                | Intrusion detection events     | `motion`     |
| `binary_sensor.{device_name}_line_crossing`            | Line crossing events           | `motion`     |
| `binary_sensor.{device_name}_region_entrance`          | Region entrance events         | `motion`     |
| `binary_sensor.{device_name}_region_exiting`           | Region exiting events          | `motion`     |
| `binary_sensor.{device_name}_scene_change`             | Scene change events            | `tamper`     |
| `binary_sensor.{device_name}_video_loss`               | Video loss events              | `problem`    |
| `binary_sensor.{device_name}_video_tampering`          | Video tampering events         | `tamper`     |
| `binary_sensor.{device_name}_tamper_detection_enabled` | Tamper detection enabled state | `tamper`     |

### Sensor Entities (Diagnostic)

| Entity ID                                        | Description          | Unit         |
| ------------------------------------------------ | -------------------- | ------------ |
| `sensor.{device_name}_cpu_utilization`           | CPU usage            | %            |
| `sensor.{device_name}_memory_usage`              | Memory usage         | %            |
| `sensor.{device_name}_device_uptime`             | Device uptime        | hours/days   |
| `sensor.{device_name}_total_reboots`             | Total reboot count   | count        |
| `sensor.{device_name}_active_streaming_sessions` | Active stream count  | count        |
| `sensor.{device_name}_streaming_clients`         | Streaming client IPs | IP addresses |

**Note**: CPU and Memory sensors display aggregated graphs with smoothed data visualization (similar to Home Assistant's system monitor).

### Other Entities

| Entity ID                            | Description     | Status      |
| ------------------------------------ | --------------- | ----------- |
| `camera.{device_name}_snapshot`      | Camera snapshot | Working     |
| `button.{device_name}_restart`       | Restart camera  | Working     |
| `media_player.{device_name}_speaker` | Audio playback  | Not Working |

---

## Home Assistant Events

When camera events occur, the integration fires `hikvision_isapi_event` events with the following data:

| Field              | Type    | Description                                   |
| ------------------ | ------- | --------------------------------------------- |
| `device`           | string  | Camera host/IP                                |
| `channel_id`       | integer | Camera channel ID                             |
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

### Event Binary Sensors Always Off

**Status**: Binary sensors are currently experiencing issues and may not update even when properly configured.

**Possible causes:**

- Event notifications not configured on camera
- "Notify Surveillance Center" not enabled in Linkage Action
- Incorrect webhook URL
- Known bug in binary sensor implementation

**Solution:**

1. Configure event notifications (see [Event Notifications Setup](#-event-notifications-setup-real-time-events))
2. Ensure webhook URL is correct: `http://YOUR_HA_IP:8123/api/hikvision_isapi`
3. Verify "Notify Surveillance Center" is enabled for each event type
4. Check camera logs for notification errors
5. Check Home Assistant logs for webhook errors

### Audio Not Working

**Status:** Media player functionality is currently not working properly.

**Workaround:** Use speaker volume control instead.

### Streaming Status Shows "Unknown"

**Status:** This should be fixed in the latest version.

**If still showing:**

- Check camera logs
- Verify camera supports streaming status endpoint
- Try restarting Home Assistant

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
