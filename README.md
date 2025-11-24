# Hikvision ISAPI Controls

![Icon](icon.png)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for Hikvision cameras using ISAPI with comprehensive control options and real-time event detection.

**⚠️ Early Development**: This integration is in early development. There are likely bugs and it's only been tested on DS-2CD2387G3 (ColorVu G3). Other models haven't been tested.

**⚠️ Disclaimer**: All written by Cursor AI. I have no clue what I'm doing.

**Known Issues**:

- Media player (speaker) functionality doesn't work properly

## Features

### Real-Time Event Detection

- **Motion Detection** - Real-time motion events (not just enabled/disabled state)
- **Intrusion Detection** - Field detection events
- **Line Crossing Detection** - Line crossing events
- **Region Entrance/Exiting** - Region-based detection events
- **Scene Change Detection** - Scene change events
- **Video Loss Detection** - Video loss events
- **Video Tampering Detection** - Tamper detection events

Events are received in real-time via webhook notifications from the camera.

### Video/Image Controls

- **Day/Night Switch** - Day, Night, or Auto mode
- **Day/Night Switch Sensitivity** - 0-7
- **Day/Night Switch Delay** - 5-120 seconds
- **Supplement Light Mode** - Smart, IR Supplement Light, or Off
- **White Light Brightness** - 0-100%
- **IR Light Brightness** - 0-100%
- **LED On Duration** - 10-300 seconds

### Motion Detection Settings

- **Motion Sensitivity** - 0-100%
- **Motion Target Type** - Human, Vehicle, or Both
- **Motion Start Trigger Time** - 0-10000ms
- **Motion End Trigger Time** - 0-10000ms

### Audio Controls

- **Speaker Volume** - 0-100%
- **Microphone Volume** - 0-100%
- **Noise Reduction** - Enable/disable noise reduction
- **Speaker** - Media player for audio playback (TTS supported) - **NOT WORKING**

### System Monitoring (Diagnostic)

- **CPU Utilization** - Current CPU usage percentage
- **Memory Usage** - Current memory usage percentage
- **Device Uptime** - Device uptime in hours/days
- **Total Reboots** - Total reboot count
- **Active Streaming Sessions** - Number of active video streams
- **Streaming Clients** - List of client IP addresses streaming

### Other

- **Snapshot Camera** - Get camera snapshots
- **Restart Button** - Remote camera restart
- **Tamper Detection Enabled** - Configuration state (if tamper detection is enabled)

## Installation

1. Copy `hikvision_isapi` folder to `config/custom_components/`
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Hikvision ISAPI Controls"
5. Enter camera IP, username (default: "admin"), password, and update interval (default: 30 seconds)

## Configuration

### Camera Setup

- ISAPI must be enabled on your camera
- User needs **Remote: Parameters Settings** permission
- Update interval: 5-300 seconds (default: 30)

### Event Notifications (Real-Time Events)

To enable real-time event detection, configure your camera to send events to Home Assistant:

1. In your camera's web interface, go to **Configuration → Event → Notification**
2. Add a new HTTP notification host:
   - **Protocol**: HTTP
   - **IP Address**: Your Home Assistant IP address
   - **Port**: 8123 (or your HA port)
   - **URL**: `/api/hikvision_isapi`
3. For each event type you want (Motion, Intrusion, etc.):
   - Go to **Event → Linkage Action**
   - Enable **Notify Surveillance Center**
   - Select the notification host you created

Once configured, binary sensors will update in real-time when events occur.

## Entities

All entities are prefixed with your device name.

### Select Entities

- `select.{device_name}_day_night_switch` - Day/Night/Auto mode
- `select.{device_name}_supplement_light` - Supplement light mode
- `select.{device_name}_motion_target_type` - Motion detection target type

### Number Entities

- `number.{device_name}_day_night_switch_sensitivity` - IR sensitivity (0-7)
- `number.{device_name}_day_night_switch_delay` - IR filter delay (5-120s)
- `number.{device_name}_speaker_volume` - Speaker volume (0-100%)
- `number.{device_name}_microphone_volume` - Microphone volume (0-100%)
- `number.{device_name}_led_on_duration` - LED duration (10-300s)
- `number.{device_name}_white_light_brightness` - White light brightness (0-100%)
- `number.{device_name}_ir_light_brightness` - IR light brightness (0-100%)
- `number.{device_name}_motion_sensitivity` - Motion sensitivity (0-100%)
- `number.{device_name}_motion_start_trigger_time` - Motion start time (0-10000ms)
- `number.{device_name}_motion_end_trigger_time` - Motion end time (0-10000ms)

### Switch Entities

- `switch.{device_name}_noise_reduction` - Noise reduction on/off

### Binary Sensor Entities (Real-Time Events)

- `binary_sensor.{device_name}_motion` - Motion detection events
- `binary_sensor.{device_name}_intrusion` - Intrusion detection events
- `binary_sensor.{device_name}_line_crossing` - Line crossing events
- `binary_sensor.{device_name}_region_entrance` - Region entrance events
- `binary_sensor.{device_name}_region_exiting` - Region exiting events
- `binary_sensor.{device_name}_scene_change` - Scene change events
- `binary_sensor.{device_name}_video_loss` - Video loss events
- `binary_sensor.{device_name}_video_tampering` - Video tampering events
- `binary_sensor.{device_name}_tamper_detection_enabled` - Tamper detection enabled state

### Sensor Entities (Diagnostic)

- `sensor.{device_name}_cpu_utilization` - CPU usage (%)
- `sensor.{device_name}_memory_usage` - Memory usage (%)
- `sensor.{device_name}_device_uptime` - Device uptime
- `sensor.{device_name}_total_reboots` - Total reboot count
- `sensor.{device_name}_active_streaming_sessions` - Active stream count
- `sensor.{device_name}_streaming_clients` - Streaming client IPs

### Other Entities

- `camera.{device_name}_snapshot` - Camera snapshot
- `button.{device_name}_restart` - Restart camera
- `media_player.{device_name}_speaker` - Audio playback (**NOT WORKING**)

## Home Assistant Events

When camera events occur, the integration fires `hikvision_isapi_event` events with the following data:

- `device`: Camera host/IP
- `channel_id`: Camera channel ID
- `camera_name`: Camera name
- `event_id`: Event type (motiondetection, intrusion, etc.)
- `detection_target`: Detection target (if applicable)
- `region_id`: Region ID (if applicable)

You can create automations based on these events:

```yaml
automation:
  - alias: "Motion Detected"
    trigger:
      platform: event
      event_type: hikvision_isapi_event
      event_data:
        event_id: motiondetection
    action:
      - service: notify.mobile_app
        data:
          message: "Motion detected on {{ trigger.event.data.camera_name }}"
```

## Requirements

- Home Assistant 2023.1+
- Hikvision camera with ISAPI enabled
- `requests` library
- `pydub>=0.25.1` (for audio - optional)

## Supported Models

- **DS-2CD2387G3 (ColorVu G3)** - Tested and working

Other models haven't been tested. May or may not work depending on ISAPI compatibility.

## Troubleshooting

**Entities not showing**:

- Check ISAPI is enabled on your camera
- Verify credentials are correct (username is case-sensitive, default is "admin")
- Check Home Assistant logs for errors

**Event binary sensors always off**:

- Configure event notifications on your camera (see Event Notifications section above)
- Ensure "Notify Surveillance Center" is enabled in Linkage Action for each event type
- Check that the webhook URL is correct: `http://YOUR_HA_IP:8123/api/hikvision_isapi`

**Audio not working**:

- Media player functionality is currently not working properly
- Use speaker volume control instead

**Streaming status shows "Unknown"**:

- This should be fixed in the latest version
- If still showing, check camera logs

## Reporting Issues

Include:

- Camera model and firmware version
- Home Assistant version
- Logs (enable debug: `logger: logs: custom_components.hikvision_isapi: debug`)
- Steps to reproduce the issue

## License

MIT
