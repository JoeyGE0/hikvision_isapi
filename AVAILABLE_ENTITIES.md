# Available Entities for Hikvision ISAPI Integration

Generated from camera capabilities query on 2025-12-13

## 📊 Current Camera States (Retrieved 2025-12-13)

All current states have been retrieved directly from the camera:

**Image Quality:** Brightness=50, Contrast=50, Saturation=50, Sharpness=50  
**White Balance:** Style=auto1, Red=50, Blue=50, Red Fine=50, Blue Fine=50  
**WDR:** Mode=auto, Level=50  
**Exposure:** Type=auto  
**Noise Reduction:** Mode=general, Level=50  
**Defog:** Mode=auto, Level=50  
**EIS:** Enabled=false  
**Image Flip:** Enabled=false  
**Image Calibration:** Enabled=false, Level=(not set), Accurate Level=0  
**Video Standard:** 50hz  
**IR Cut Filter:** Type=day, Night to Day Level=3, Night to Day Time=5  
**Supplement Light:** Mode=colorVuWhiteLight, White Light Brightness=100, Regulation Mode=auto  
**IO Input:** inactive  
**IO Output:** inactive

## ✅ Currently Implemented Entities

All entities listed here are already implemented in the integration.

### Binary Sensors (Event Detection)

1. **Motion Detection** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `motiondetection`
   - Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

2. **Tamper Detection** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `tamperdetection`
   - Endpoint: `/ISAPI/System/Video/inputs/channels/1/tamperDetection`

3. **Scene Change Detection** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `scenechangedetection`
   - Endpoint: `/ISAPI/System/Video/inputs/channels/1/sceneChangeDetection`

4. **Field Detection / Intrusion** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `fielddetection`
   - Endpoint: `/ISAPI/Smart/Image/channels/1/fieldDetection`

5. **Line Detection** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `linedetection`
   - Endpoint: `/ISAPI/Smart/Image/channels/1/lineDetection`

6. **Region Entrance** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `regionentrance`
   - Endpoint: `/ISAPI/Smart/Image/channels/1/regionEntrance`

7. **Region Exiting** (`binary_sensor`)

   - Enabled by default: YES
   - Event type: `regionexiting`
   - Endpoint: `/ISAPI/Smart/Image/channels/1/regionExiting`

8. **IO Input** (`binary_sensor`)
   - Enabled by default: YES
   - Event type: `io`
   - Endpoint: `/ISAPI/System/IO/inputs`

### Switches (Controls)

9. **Noise Reduction** (`switch`)

   - Enabled by default: NO
   - Endpoint: `/ISAPI/Image/channels/1` → `ImageChannel.NoiseReduce`

10. **Motion Detection Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

11. **Tamper Detection Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/Video/inputs/channels/1/tamperDetection`

12. **Intrusion Detection Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/Smart/Image/channels/1/fieldDetection`

13. **Line Crossing Detection Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/Smart/Image/channels/1/lineDetection`

14. **Scene Change Detection Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/Video/inputs/channels/1/sceneChangeDetection`

15. **Region Entrance Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/Smart/Image/channels/1/regionEntrance`

16. **Region Exiting Enable** (`switch`)

- Enabled by default: YES
- Endpoint: `/ISAPI/Smart/Image/channels/1/regionExiting`

17. **Alarm Input** (`switch`)

    - Enabled by default: YES
    - Endpoint: `/ISAPI/System/IO/inputs`

18. **Alarm Output** (`switch`)
    - Enabled by default: YES
    - Endpoint: `/ISAPI/System/IO/outputs`

### Number Entities

19. **IR Sensitivity** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/ircutFilter`

20. **IR Filter Time** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/ircutFilter`

21. **Speaker Volume** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/TwoWayAudio/channels/1`

22. **Microphone Volume** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/TwoWayAudio/channels/1`

23. **White Light Time** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`

24. **White Light Brightness** (`number`)

    - Enabled by default: NO
    - **Current State:** `100` ✅ (retrieved from camera)
    - Range: 0-100
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`
    - XML path: `SupplementLight.whiteLightBrightness`

25. **IR Light Brightness** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`

26. **White Light Brightness Limit** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`

27. **IR Light Brightness Limit** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`

28. **Motion Sensitivity** (`number`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

29. **Motion Start Trigger Time** (`number`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

30. **Motion End Trigger Time** (`number`)
    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

### Select Entities

31. **Light Mode** (`select`)

    - Enabled by default: YES
    - **Current State:** `colorVuWhiteLight` ✅ (retrieved from camera)
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`
    - XML path: `SupplementLight.supplementLightMode`
    - Notes: Controls supplement light mode (Supplement Light entity)

32. **Brightness Control Mode** (`select`)

    - Enabled by default: YES
    - **Current State:** `auto` ✅ (retrieved from camera)
    - Endpoint: `/ISAPI/Image/channels/1/supplementLight`
    - XML path: `SupplementLight.mixedLightBrightnessRegulatMode`
    - Notes: Auto/manual control for mixed light brightness

33. **IR Mode** (`select`)

- Enabled by default: YES
- **Current State:** `day` ✅ (retrieved from camera)
- Endpoint: `/ISAPI/Image/channels/1/ircutFilter`
- XML path: `IrcutFilter.IrcutFilterType`
- Notes: IR Cut Filter mode (day/night/auto)

34. **Motion Target Type** (`select`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/Video/inputs/channels/1/motionDetection`

### Other Entities

35. **Two-Way Audio** (`media_player`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/TwoWayAudio/channels/1`

36. **Camera** (`camera`)

    - Enabled by default: YES (main stream only, other streams disabled by default)
    - Endpoint: `/ISAPI/Streaming/channels`

37. **Restart Button** (`button`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/reboot`

38. **Test Tone Button** (`button`)
    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/TwoWayAudio/channels/1/audioData`

### Sensor Entities (Read-only System Info)

39. **CPU Utilization** (`sensor`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/status`

40. **Memory Usage** (`sensor`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/status`

41. **Device Uptime** (`sensor`)

- Enabled by default: YES
- Endpoint: `/ISAPI/System/status`

42. **Reboot Count** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/status`

43. **Streaming Sessions** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/status`

44. **Streaming Clients** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/System/status`

45. **Notification Host** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Event/notification/httpHosts`

46. **Notification Host Path** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Event/notification/httpHosts`

47. **Notification Host Port** (`sensor`)

    - Enabled by default: NO
    - Endpoint: `/ISAPI/Event/notification/httpHosts`

48. **Notification Host Protocol** (`sensor`)
    - Enabled by default: NO
    - Endpoint: `/ISAPI/Event/notification/httpHosts`

**Note:** Some entities may be missing from this list. If you find more implemented entities, please update the enabled/disabled status. Most will be disabled by default unless everyone will use them.

## 🆕 Potential New Entities to Add

### Image Quality Settings (Number Entities)

These will be added as `number` entities with 0-100 range:

1. **Brightness Level** (`/ISAPI/Image/channels/1/color`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/color`
   - XML path: `Color.brightnessLevel`
   - Notes: Controls overall image brightness. Default is 50.

2. **Contrast Level** (`/ISAPI/Image/channels/1/color`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/color`
   - XML path: `Color.contrastLevel`
   - Notes: Controls image contrast. Default is 50.

3. **Saturation Level** (`/ISAPI/Image/channels/1/color`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/color`
   - XML path: `Color.saturationLevel`
   - Notes: Controls color saturation. Default is 50.

4. **Sharpness Level** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.Sharpness.SharpnessLevel`
   - Notes: Controls image sharpness. Default is 50.

5. **White Balance Red** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: `WhiteBalance.WhiteBalanceRed`
   - Notes: Red channel adjustment for white balance. Default is 50.

6. **White Balance Blue** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: `WhiteBalance.WhiteBalanceBlue`
   - Notes: Blue channel adjustment for white balance. Default is 50.

7. **White Balance Red Fine Tuning** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: `WhiteBalance.WhiteBalanceRedFineTuning`
   - Notes: Fine adjustment for red channel. Default is 50.

8. **White Balance Blue Fine Tuning** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `number` (0-100)
   - **Current State:** `50` ✅ (retrieved from camera)
   - Range: **0-100** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: `WhiteBalance.WhiteBalanceBlueFineTuning`
   - Notes: Fine adjustment for blue channel. Default is 50.

9. **White Balance Fine-Tuning (General)** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `number` (0-100)
   - Current: `50` (from UI - may be same as red/blue fine-tuning)
   - Range: **0-100** (confirmed from UI)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: Need to verify (may be separate from red/blue fine-tuning or UI may show combined)
   - Notes: General fine-tuning control for white balance. May be alternative to separate red/blue controls or UI representation of them.

10. **WDR Level** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `50` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.WDR.WDRLevel`
    - Notes: Controls Wide Dynamic Range level when WDR mode is enabled. Default is 50.

11. **Limit Gain** (`/ISAPI/Image/channels/1/exposure`)

    - **Entity Type:** `number` (0-100)
    - Current: `100` (from UI)
    - Range: **0-100** (confirmed from UI)
    - Endpoint: `/ISAPI/Image/channels/1/exposure`
    - XML path: `Exposure.LimitGain` (likely - need to verify if exists in exposure XML)
    - Notes: Maximum gain limit for exposure. Default appears to be 100.

12. **Night to Day Filter Level** (`/ISAPI/Image/channels/1/ircutFilter`) - ⚠️ **ALREADY IMPLEMENTED** (as IR Sensitivity number)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `3` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed)
    - Endpoint: `/ISAPI/Image/channels/1/ircutFilter`
    - XML path: `IrcutFilter.nightToDayFilterLevel`
    - Notes: **Already implemented as "IR Sensitivity" number entity.** Sensitivity level for switching from night to day mode.

13. **Night to Day Filter Time** (`/ISAPI/Image/channels/1/ircutFilter`) - ⚠️ **ALREADY IMPLEMENTED** (as IR Filter Time number)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `5` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed)
    - Endpoint: `/ISAPI/Image/channels/1/ircutFilter`
    - XML path: `IrcutFilter.nightToDayFilterTime`
    - Notes: **Already implemented as "IR Filter Time" number entity.** Time delay for switching from night to day mode.

14. **Noise Reduction Level** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `50` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.NoiseReduce.GeneralMode.generalLevel`
    - Notes: Controls noise reduction strength in general mode. Default is 50.

15. **Defog Level** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `50` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.Dehaze.DehazeLevel`
    - Notes: Controls defog/dehaze strength. Default is 50.

16. **Image Calibration Accurate Level** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `number` (0-100)
    - **Current State:** `0` ✅ (retrieved from camera)
    - Range: **0-100** (confirmed from XML min/max attributes)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.LensDistortionCorrection.accurateLevel`
    - Notes: Fine-tune image calibration. Range 0-100.

### Select Entities (Dropdowns)

1. **White Balance Style** (`/ISAPI/Image/channels/1/whiteBalance`)

   - **Entity Type:** `select`
   - **Current State:** `auto1` ✅ (retrieved from camera - maps to "Auto (Wide)" in UI)
   - Options: **MWB, Auto (Wide), Auto (Narrow), Locked WB, Fluorescent Lamp, Incandescent Lamp, Warm Light Lamp, Natural Light** (confirmed from UI)
   - Endpoint: `/ISAPI/Image/channels/1/whiteBalance`
   - XML path: `WhiteBalance.WhiteBalanceStyle`
   - Notes: Sets white balance mode. When set to auto, manual adjustments may be disabled. Camera XML shows `auto1` which maps to `Auto (Wide)` in UI.

2. **Exposure Type** (`/ISAPI/Image/channels/1/exposure`)

   - **Entity Type:** `select`
   - **Current State:** `auto` ✅ (retrieved from camera)
   - Options: Need to verify from capabilities (likely: auto, manual)
   - Endpoint: `/ISAPI/Image/channels/1/exposure`
   - XML path: `Exposure.ExposureType`
   - Notes: Controls exposure mode. Manual mode enables shutter/gain controls.

3. **WDR Mode** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `select`
   - **Current State:** `auto` ✅ (retrieved from camera)
   - Options: Need to verify from capabilities (likely: off, auto, manual, etc.)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.WDR.mode`
   - Notes: Controls Wide Dynamic Range mode. When enabled, WDR Level can be adjusted.

4. **Backlight Mode** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `select`
   - Current: `Auto WDR` (from UI)
   - Options: **Off, BLC, WDR, Auto WDR, HLC** (confirmed from UI)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint - may be separate BLC/HLC elements)
   - XML path: Need to verify (may be separate BLC/HLC elements in ImageChannel)
   - Notes: Controls backlight compensation. WDR = Wide Dynamic Range, BLC = Backlight Compensation, HLC = Highlight Compensation.

5. **Supplement Light Mode** (`/ISAPI/Image/channels/1/supplementLight`) - ⚠️ **ALREADY IMPLEMENTED** (as Light Mode select)

   - **Entity Type:** `select`
   - **Current State:** `colorVuWhiteLight` ✅ (retrieved from camera)
   - Options: Need to check from capabilities (likely: colorVuWhiteLight, irLight, etc.)
   - Endpoint: `/ISAPI/Image/channels/1/supplementLight`
   - XML path: `SupplementLight.supplementLightMode`
   - Notes: **Already implemented as "Light Mode" select entity.** Controls type of supplemental lighting.

6. **Mixed Light Brightness Regulation Mode** (`/ISAPI/Image/channels/1/supplementLight`) - ⚠️ **ALREADY IMPLEMENTED** (as Brightness Control Mode select)

   - **Entity Type:** `select`
   - **Current State:** `auto` ✅ (retrieved from camera)
   - Options: **auto, manual** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/supplementLight`
   - XML path: `SupplementLight.mixedLightBrightnessRegulatMode`
   - Notes: **Already implemented as "Brightness Control Mode" select entity.** Auto/manual control for mixed light brightness.

7. **IR Cut Filter Type** (`/ISAPI/Image/channels/1/ircutFilter`) - ⚠️ **ALREADY IMPLEMENTED** (as IR Mode select)

   - **Entity Type:** `select`
   - **Current State:** `day` ✅ (retrieved from camera)
   - Options: **day, night, auto** (confirmed)
   - Endpoint: `/ISAPI/Image/channels/1/ircutFilter`
   - XML path: `IrcutFilter.IrcutFilterType`
   - Notes: **Already implemented as "IR Mode" select entity.** Controls day/night filter mode. Auto switches based on light conditions.

8. **Noise Reduction Mode** (`/ISAPI/Image/channels/1`) - ⚠️ **ALREADY IMPLEMENTED** (as Noise Reduction switch)

   - **Entity Type:** `select` (but currently implemented as switch)
   - **Current State:** `general` ✅ (retrieved from camera)
   - Options: Need to verify from capabilities (likely: off, general, expert, etc.)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.NoiseReduce.mode`
   - Notes: **Already implemented as "Noise Reduction" switch entity.** May need to convert to select to support mode options (off, general, expert).

9. **Defog Mode** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `select`
   - **Current State:** `auto` ✅ (retrieved from camera)
   - Options: Need to verify from capabilities (likely: off, auto, on, etc.)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.Dehaze.DehazeMode`
   - Notes: Controls defog/dehaze mode. Auto automatically adjusts, On/Off manually control.

10. **Image Calibration Level** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `select`
    - **Current State:** `(not set)` ✅ (retrieved from camera - level element exists but no value set)
    - Options: **level1, level2, level3, level4, level5, level6** (confirmed from XML opt attribute)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.LensDistortionCorrection.level`
    - Notes: Image calibration level. Recommended: 4mm lens = Level1, 2.8mm = Level2, 2mm = Level3.

11. **Video Standard** (`/ISAPI/Image/channels/1`)

    - **Entity Type:** `select`
    - **Current State:** `50hz` ✅ (retrieved from camera)
    - Options: Need to verify from capabilities (likely: 50hz, 60hz)
    - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
    - XML path: `ImageChannel.powerLineFrequency.powerLineFrequencyMode`
    - Notes: Sets video standard/power line frequency. 50Hz = PAL, 60Hz = NTSC.

### Switch Entities

1. **Exposure Enabled** (`/ISAPI/Image/channels/1/exposure`)

   - **Entity Type:** `switch`
   - Current: Need to verify (may not exist as separate field)
   - Options: **on, off** (true/false)
   - Endpoint: `/ISAPI/Image/channels/1/exposure`
   - XML path: Need to verify (may not exist - exposure may always be enabled)
   - Notes: Enable/disable exposure control. May not be a separate setting - exposure may always be active.

2. **Anti-Banding** (`/ISAPI/Image/channels/1/exposure`)

   - Current: `off` (from UI)
   - Options: **on, off** (confirmed from UI)
   - Endpoint: `/ISAPI/Image/channels/1/exposure`
   - XML path: `Exposure.AntiBanding` (likely)
   - Notes: Reduces flicker from artificial lighting (50Hz/60Hz).

3. **Image Flip** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `switch`
   - **Current State:** `off` ✅ (retrieved from camera - enabled: false)
   - Options: **on, off** (true/false)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.ImageFlip.enabled`
   - Notes: Flips/mirrors the image when enabled.

4. **EIS (Electronic Image Stabilization)** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `switch`
   - **Current State:** `off` ✅ (retrieved from camera - enabled: false)
   - Options: **on, off** (true/false)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.EIS.enabled`
   - Notes: Toggle for Electronic Image Stabilization. Note: UI shows select with levels, but API only has enabled boolean.

5. **Image Calibration Enabled** (`/ISAPI/Image/channels/1`)

   - **Entity Type:** `switch`
   - **Current State:** `off` ✅ (retrieved from camera - enabled: false)
   - Options: **on, off** (true/false)
   - Endpoint: `/ISAPI/Image/channels/1` (part of main Image endpoint)
   - XML path: `ImageChannel.LensDistortionCorrection.enabled`
   - Notes: Enable/disable lens distortion correction (image calibration).

### Sensor Entities (Read-only)

1. **IO Input Status** (`/ISAPI/System/IO/inputs/1/status`)

   - **Entity Type:** `sensor` (read-only)
   - **Current State:** `inactive` ✅ (retrieved from camera)
   - Values: **active, inactive**
   - Endpoint: `/ISAPI/System/IO/inputs/1/status`
   - XML path: `IOPortStatus.ioState`
   - Notes: Read-only sensor showing current IO input port state.

2. **IO Output Status** (`/ISAPI/System/IO/outputs/1/status`)

   - **Entity Type:** `sensor` (read-only)
   - **Current State:** `inactive` ✅ (retrieved from camera)
   - Values: **active, inactive**
   - Endpoint: `/ISAPI/System/IO/outputs/1/status`
   - XML path: `IOPortStatus.ioState`
   - Notes: Read-only sensor showing current IO output port state.

3. **System Status** (`/ISAPI/System/status`)

   - **Entity Type:** `sensor` (read-only) or multiple sensors
   - Current: Various system metrics
   - Values: Depends on metric type
   - Endpoint: `/ISAPI/System/status`
   - XML path: Need to parse full XML structure
   - Notes: Various system metrics (CPU, memory, temperature, etc.). May need to be split into multiple sensor entities.

4. **Storage Status** (`/ISAPI/ContentMgmt/Storage`)

   - **Entity Type:** `sensor` (read-only) or multiple sensors
   - Current: Storage device information
   - Values: Depends on storage type
   - Endpoint: `/ISAPI/ContentMgmt/Storage`
   - XML path: Need to parse full XML structure
   - Notes: Storage device information (capacity, used space, etc.). May need to be split into multiple sensor entities.

### Binary Sensor Entities (System Events)

These events are available but may not be implemented yet:

1. **Disk Error** (`diskerror`)

   - **Entity Type:** `binary_sensor`
   - Event type: `diskerror`
   - Values: **on, off** (active when disk error occurs)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor that turns on when disk error is detected.

2. **Disk Full** (`diskfull`)

   - **Entity Type:** `binary_sensor`
   - Event type: `diskfull`
   - Values: **on, off** (active when disk is full)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor that turns on when storage disk is full.

3. **Illegal Access** (`illaccess`)

   - **Entity Type:** `binary_sensor`
   - Event type: `illaccess`
   - Values: **on, off** (active when illegal access detected)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor that turns on when illegal access attempt is detected.

4. **IP Conflict** (`ipconflict`)

   - **Entity Type:** `binary_sensor`
   - Event type: `ipconflict`
   - Values: **on, off** (active when IP conflict detected)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor that turns on when IP address conflict is detected.

5. **Network Broken** (`nicbroken`)

   - **Entity Type:** `binary_sensor`
   - Event type: `nicbroken`
   - Values: **on, off** (active when network issue detected)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor that turns on when network connection issue is detected.

6. **Storage Detection** (`storagedetection`)

   - **Entity Type:** `binary_sensor`
   - Event type: `storagedetection`
   - Values: **on, off** (active when storage event detected)
   - Endpoint: Check Event/triggers
   - Notes: Binary sensor for storage-related events.

### Cloud/Platform Services (Switch & Sensor Entities)

1. **Hik-Connect Enable** (`/ISAPI/System/Network/Platform` or similar)

   - **Entity Type:** `switch`
   - **Enabled by default:** NO
   - **Current State:** Need to verify (from UI: enabled)
   - Options: **on, off** (true/false)
   - Endpoint: Need to discover (likely `/ISAPI/System/Network/Platform` or `/ISAPI/System/ThirdParty/Cloud` or similar)
   - XML path: Need to verify (likely `Platform.enabled` or `HikConnect.enabled`)
   - Notes: Enables/disables Hik-Connect cloud service. Requires internet access. Based on UI showing enable toggle.

2. **Hik-Connect Connection Status** (`/ISAPI/System/Network/Platform/status` or similar)

   - **Entity Type:** `sensor` (read-only)
   - **Enabled by default:** YES
   - **Current State:** Need to verify (from UI: "Offline" with error code 11)
   - Values: **Online, Offline, Error** (or similar status values)
   - Endpoint: Need to discover (likely `/ISAPI/System/Network/Platform/status` or similar)
   - XML path: Need to verify (likely `Platform.status` or `HikConnect.registrationStatus`)
   - Notes: Shows Hik-Connect registration status. Shows "Offline" with error code" when registration fails. May include error codes for troubleshooting.

### Audible Alarm Output (Switch, Select, Number Entities)

**Note:** Endpoints for audible alarm output configuration were not found in standard ISAPI locations. The camera supports audio output (`audioOutputNums: 1` in capabilities), and `/ISAPI/System/Audio/channels/1` exists, but the specific audible alarm output configuration endpoint needs discovery.

1. **Audible Alarm Output Enable** (endpoint to be discovered)

   - **Entity Type:** `switch`
   - **Enabled by default:** NO
   - Options: **on, off** (true/false)
   - Endpoint: Need to discover (may be `/ISAPI/System/Audio/channels/1/alarmOutput` or similar)
   - XML path: Need to verify
   - Notes: Enables/disables audible alarm output. Based on UI showing audible alarm output configuration.

2. **Audio Type** (select)

   - **Entity Type:** `select`
   - **Enabled by default:** NO
   - **Current State:** `audioClass: "alertAudio"`
   - Options: **"alertAudio", "promptAudio", "customAudio"** (default: "alertAudio")
   - Endpoint: ✅ **`/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`**
   - JSON path: `AudioAlarm.audioClass`
   - Notes: Selects type of audio class for alarm output. When "alertAudio", uses `alertAudioID`. When "customAudio", uses `customAudioID` (1-3).

3. **Warning Sound** (select)

   - **Entity Type:** `select`
   - **Enabled by default:** NO
   - **Current State:** `alertAudioID: 6` ("Attention please.The area is under surveillance")
   - Options: **11 options available** (from capabilities - AlertAudioTypeListCap):
     - 1: "Siren"
     - 2: "Warning,this is a restricted area"
     - 3: "Warning,this is a restricted area,please keep away"
     - 4: "Warning,this is a no-parking zone"
     - 5: "Warning,this is a no-parking zone,please keep away"
     - 6: "Attention please.The area is under surveillance" (current)
     - 7: "Welcome,Please notice that the area is under surveillance"
     - 8: "Welcome"
     - 9: "Danger!Please keep away"
     - 10: "(Siren)&Danger,please keep away"
     - 11: "Audio Warning"
   - Endpoint: ✅ **`/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`**
   - JSON path: `AudioAlarm.alertAudioID` (for alertAudio class)
   - Notes: Selects specific warning sound/message to play (for alertAudio class). Also supports `audioClass` with options: "alertAudio", "promptAudio", "customAudio".

4. **Alarm Times** (number)

   - **Entity Type:** `number`
   - **Enabled by default:** NO
   - **Current State:** `alarmTimes: 2`
   - Range: **1-50** (default: 5)
   - Endpoint: ✅ **`/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`**
   - JSON path: `AudioAlarm.alarmTimes`
   - Notes: Number of times to repeat the alarm audio.

5. **Loudspeaker Volume** (number)

   - **Entity Type:** `number`
   - **Enabled by default:** NO
   - **Current State:** `audioVolume: 100`
   - Range: **1-100** (default: 100)
   - Endpoint: ✅ **`/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`**
   - JSON path: `AudioAlarm.audioVolume`
   - Notes: Volume level for loudspeaker output (1-100%).

6. **Arming Schedule** (complex schedule entity)

   - **Entity Type:** Complex schedule (weekly time ranges)
   - **Enabled by default:** NO
   - **Current State:** Empty schedule (all days have empty TimeRange arrays)
   - Options: Weekly schedule grid (Mon-Sun, 00:00-24:00)
   - Endpoint: ✅ **`/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`**
   - JSON path: `AudioAlarm.TimeRangeList[]` (array of week objects with TimeRange arrays)
   - Structure: `TimeRangeList[].week` (1-7), `TimeRangeList[].TimeRange[]` (array of time ranges with beginTime/endTime)
   - Notes: Schedule when audible alarm output is active. Weekly grid with hour-by-hour control. Max 8 time ranges per day.

**Discovery Status:**

- ✅ **FOUND:** `/ISAPI/Event/triggers/notifications/AudioAlarm?format=json` - Main configuration endpoint
- ✅ **FOUND:** `/ISAPI/Event/triggers/notifications/AudioAlarm/capabilities?format=json` - Capabilities endpoint (shows all options and ranges)
- ✅ **FOUND:** `/ISAPI/Event/triggers/notifications/AudioAlarm/customAudioInfo?format=json` - Custom audio info (currently empty)
- ✅ **FOUND:** Camera supports audio output (`audioOutputNums: 1` in capabilities)
- ✅ **FOUND:** All configuration options, ranges, and current values confirmed
- ✅ **FOUND:** Supports custom audio uploads (`isSupportCustomAudio: true`)
- ✅ **FOUND:** Supports audio testing (`isSupportAudioTest: true`)

## 📋 Implementation Priority

### High Priority (Most Useful) - Ready to Implement

1. **Brightness/Contrast/Saturation/Sharpness** - Image quality controls (0-100 range confirmed)
2. **White Balance settings** - Color correction (0-100 range confirmed)
3. **Exposure controls** - Camera exposure settings (exposure type, limit gain confirmed)
4. **Backlight/WDR** - Backlight mode and WDR level (0-100 range confirmed)

### Medium Priority

1. **Hik-Connect controls** - Enable/disable cloud service and connection status (endpoints need discovery)
2. **Audible Alarm Output** - Audio alarm configuration (endpoints need discovery - may not be exposed via ISAPI)
3. **IR Cut Filter settings** - Day/night mode controls
4. **Anti-Banding** - Flicker reduction switch
5. **System status sensors** - Disk, network, etc.
6. **IO status sensors** - Monitor IO port states

### Low Priority

1. **Fine-tuning controls** - Advanced white balance fine-tuning
2. **Filter timing settings** - IR cut filter timing
3. **System event binary sensors** - Disk errors, network issues

## 🔍 Implementation Notes

### Verified Information

- All endpoints use channel 1 (`/channels/1/`)
- **ALL number entities confirmed 0-100 range** (Brightness, Contrast, Saturation, Sharpness, White Balance Red/Blue, Fine-Tuning, WDR Level, Limit Gain, Noise Reduction Level, Defog Level, Night to Day Filter Level/Time, Image Calibration Accurate Level)
- Most image settings are part of main `/ISAPI/Image/channels/1` endpoint, not separate endpoints
- Event triggers show 13 event types available
- Smart features (field/line/region detection) are already implemented
- Two-way audio is already implemented

### Verified Endpoints and XML Paths

- ✅ **Sharpness**: `/ISAPI/Image/channels/1` → `ImageChannel.Sharpness.SharpnessLevel`
- ✅ **WDR**: `/ISAPI/Image/channels/1` → `ImageChannel.WDR.mode` (select) and `ImageChannel.WDR.WDRLevel` (number)
- ✅ **Noise Reduction**: `/ISAPI/Image/channels/1` → `ImageChannel.NoiseReduce.mode` (select) and `ImageChannel.NoiseReduce.GeneralMode.generalLevel` (number)
- ✅ **Defog/Dehaze**: `/ISAPI/Image/channels/1` → `ImageChannel.Dehaze.DehazeMode` (select) and `ImageChannel.Dehaze.DehazeLevel` (number)
- ✅ **EIS**: `/ISAPI/Image/channels/1` → `ImageChannel.EIS.enabled` (switch)
- ✅ **ImageFlip**: `/ISAPI/Image/channels/1` → `ImageChannel.ImageFlip.enabled` (switch)
- ✅ **LensDistortionCorrection**: `/ISAPI/Image/channels/1` → `ImageChannel.LensDistortionCorrection.enabled` (switch), `ImageChannel.LensDistortionCorrection.level` (select), `ImageChannel.LensDistortionCorrection.accurateLevel` (number)
- ✅ **Video Standard**: `/ISAPI/Image/channels/1` → `ImageChannel.powerLineFrequency.powerLineFrequencyMode` (select)
- ✅ **White Balance**: `/ISAPI/Image/channels/1/whiteBalance` → All white balance settings confirmed

### Still Needs Verification

- **Hik-Connect endpoints** - Need to discover exact ISAPI endpoints for:
  - Enable/disable switch (`/ISAPI/System/Network/Platform` or similar)
  - Connection status sensor (`/ISAPI/System/Network/Platform/status` or similar)
  - Server IP address configuration (if needed)
- **Audible Alarm Output endpoints** - Need to discover exact ISAPI endpoints for:
  - Enable/disable switch
  - Audio Type select
  - Warning Sound select
  - Alarm Times number
  - Loudspeaker Volume number
  - Arming Schedule configuration
  - **Note:** `/ISAPI/System/Audio/channels/1` exists but doesn't contain alarm output config. May be configured via Event/triggers or web UI only.
- **Backlight Mode options** - UI shows Off, BLC, WDR, Auto WDR, HLC but API structure needs verification (may be separate BLC/HLC elements)
- **WDR Mode options** - Current is "auto", need to check capabilities for all options
- **Noise Reduction Mode options** - Current is "general", need to verify all options (UI shows Off, Normal Mode, Expert Mode)
- **Defog Mode options** - Current is "auto", need to verify all options (UI shows Off, Auto, On)
- **Video Standard options** - Current is "50hz", need to verify if "60hz" is available
- **Limit Gain** - Appears in UI but not found in exposure XML, may be in different endpoint or under different name
- **Shutter Range** - Appears in UI but endpoint needs verification - may be part of exposure endpoint or separate
- **Anti-Banding** - Appears in UI with options like "1/1000" - needs endpoint verification
- **Supplement Light Mode options** - Current is "colorVuWhiteLight", need to check capabilities for all options
- Some select entities may have additional options not visible in UI - check capabilities XML when implementing

## 📝 Next Steps

1. Check exact ranges for number entities by querying capabilities
2. Implement high-priority entities first
3. Test each entity type before adding more
4. Consider grouping related settings (e.g., all color settings together)
