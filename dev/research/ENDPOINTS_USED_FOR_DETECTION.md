# Endpoints Used for Feature Detection

This document lists all endpoints used in the feature detection code for comparison with the ISAPI PDF.

## Detection Endpoints

### 1. Image Adjustment
- **Endpoint:** `GET /ISAPI/Image/channels/{channel}/color`
- **Purpose:** Detect if brightness, contrast, saturation controls exist
- **Used in:** `detect_features()` line 2963

### 2. Two-way Audio
- **Endpoint:** `GET /ISAPI/System/TwoWayAudio/channels/{channel}`
- **Purpose:** Detect if two-way audio is supported
- **Used in:** `detect_features()` line 2966

### 3. Lights (Supplement Light)
- **Endpoint:** `GET /ISAPI/Image/channels/{channel}/supplementLight`
- **Purpose:** Detect if light controls exist
- **Used in:** `detect_features()` line 2969

### 4. IR Cut Filter
- **Endpoint:** `GET /ISAPI/Image/channels/{channel}/IrcutFilter`
- **Purpose:** Detect if IR cut filter (day/night mode) exists
- **Used in:** `detect_features()` line 2972

### 5. Audio Alarm
- **Endpoint:** `GET /ISAPI/Event/triggers/notifications/AudioAlarm?format=json`
- **Purpose:** Detect if audio alarm configuration exists
- **Used in:** `detect_features()` line 2975
- **Note:** Uses JSON format (XML version returns 404)

### 6. Motion Detection
- **Method:** Check capabilities XML flag
- **Path:** `EventCap/isSupportMotionDetection`
- **Used in:** `detect_features()` line 2978-2980

### 7. Tamper Detection
- **Method:** Check capabilities XML flag
- **Path:** `EventCap/isSupportTamperDetection`
- **Used in:** `detect_features()` line 2983-2985

### 8. Intrusion Detection
- **Endpoint:** `GET /ISAPI/Event/triggers/intrusionDetection`
- **Purpose:** Detect if intrusion detection exists
- **Used in:** `detect_features()` line 2986

### 9. Line Detection
- **Endpoint:** `GET /ISAPI/Event/triggers/lineDetection`
- **Purpose:** Detect if line crossing detection exists
- **Used in:** `detect_features()` line 2989

### 10. Region Entrance
- **Endpoint:** `GET /ISAPI/Event/triggers/regionEntrance`
- **Purpose:** Detect if region entrance detection exists
- **Used in:** `detect_features()` line 2992

### 11. Region Exiting
- **Endpoint:** `GET /ISAPI/Event/triggers/regionExiting`
- **Purpose:** Detect if region exiting detection exists
- **Used in:** `detect_features()` line 2995

### 12. Scene Change Detection
- **Endpoint:** `GET /ISAPI/Event/triggers/sceneChangeDetection`
- **Purpose:** Detect if scene change detection exists
- **Used in:** `detect_features()` line 2998

### 13. I/O Ports
- **Method:** Check capabilities XML
- **Path:** `IOCap/IOInputPortNums` and `IOCap/IOOutputPortNums`
- **Used in:** `detect_features()` line 3001-3002

## Other Endpoints Used in Integration (Not Detection)

### Capabilities
- `GET /ISAPI/System/capabilities` - Used for capabilities XML parsing

### Two-way Audio (Operations)
- `GET /ISAPI/System/TwoWayAudio/channels/{channel}` - Get audio settings
- `PUT /ISAPI/System/TwoWayAudio/channels/{channel}` - Set audio settings
- `PUT /ISAPI/System/TwoWayAudio/channels/{channel}/open` - Open audio session
- `PUT /ISAPI/System/TwoWayAudio/channels/{channel}/close` - Close audio session
- `PUT /ISAPI/System/TwoWayAudio/channels/{channel}/audioData?sessionId={id}` - Send audio data

### Event Triggers
- `GET /ISAPI/Event/triggers` - Get all event triggers
- `GET /ISAPI/Event/triggers/notifications/AudioAlarm?format=json` - Get audio alarm config
- `PUT /ISAPI/Event/triggers/notifications/AudioAlarm?format=json` - Set audio alarm config
- `PUT /ISAPI/Event/triggers/notifications/AudioAlarm/{audioID}/test?format=json` - Test audio alarm

## Notes

- All endpoints use channel number from `self.channel` (defaults to 1)
- Detection endpoints return:
  - 200 = Feature exists and accessible
  - 403 = Feature exists but no permission (still means feature exists)
  - 404 = Feature doesn't exist (not supported)
- EventCap flags are checked from capabilities XML (standard ISAPI)
- I/O ports are checked from capabilities XML (standard ISAPI)

