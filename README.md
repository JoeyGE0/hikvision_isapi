# Hikvision ISAPI Controls

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for Hikvision cameras using ISAPI.

**⚠️ Early Development**: This integration is in early development. There are likely bugs and it's only been tested on DS-2CD2387G3 (ColorVu G3). Other models haven't been tested. All written by Cursor AI. I have no clue what im doing.

**Known Issues**:

- Media player (speaker) functionality doesn't work properly

## Features

- Day/Night Switch (Day, Night, Auto)
- Day/Night Switch Sensitivity (0-7)
- Day/Night Switch Delay (5-120 seconds)
- Supplement Light (Smart, IR Supplement Light, Off)
- LED On Duration (10-300 seconds)
- Speaker - Media player for audio playback (TTS supported) - **NOT WORKING**
- Speaker Volume (0-100%)
- Microphone Volume (0-100%)
- Motion Detection (binary sensor)
- Tamper Detection (binary sensor)
- Snapshot Camera
- Restart Button

All control entities have corresponding read-only sensors.

## Installation

1. Copy `hikvision_isapi` folder to `config/custom_components/`
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Hikvision ISAPI Controls"
5. Enter camera IP, username, password, and update interval (default 30 seconds)

## Configuration

- ISAPI must be enabled on your camera
- User needs Remote: Parameters Settings permission
- Update interval: 5-300 seconds (default 30)

Select and number entities update immediately in the UI, then sync with the camera in the background.

## Entities

All entities are prefixed with your device name.

- `select.{device_name}_day_night_switch`
- `select.{device_name}_supplement_light`
- `number.{device_name}_day_night_switch_sensitivity`
- `number.{device_name}_day_night_switch_delay`
- `number.{device_name}_speaker_volume`
- `number.{device_name}_microphone_volume`
- `number.{device_name}_led_on_duration`
- `sensor.{device_name}_day_night_switch`
- `sensor.{device_name}_day_night_switch_sensitivity`
- `sensor.{device_name}_day_night_switch_delay`
- `sensor.{device_name}_supplement_light`
- `sensor.{device_name}_speaker_volume`
- `sensor.{device_name}_mic_volume`
- `sensor.{device_name}_led_on_duration`
- `binary_sensor.{device_name}_motion_detection`
- `binary_sensor.{device_name}_tamper_detection`
- `camera.{device_name}_snapshot`
- `media_player.{device_name}_speaker`
- `button.{device_name}_restart`

## Requirements

- Home Assistant 2023.1+
- Hikvision camera with ISAPI
- `requests`
- `pydub>=0.25.1` (for audio)

## Supported Models

- DS-2CD2387G3 (ColorVu G3) - only model tested

Other models haven't been tested. May or may not work.

## Troubleshooting

**Entities not showing**: Check ISAPI is enabled and credentials are correct. Check logs.

**Audio not working**: 


## Reporting Issues

Include:

- Camera model and firmware
- Home Assistant version
- Logs (enable debug: `logger: logs: custom_components.hikvision_isapi: debug`)

## License

MIT
