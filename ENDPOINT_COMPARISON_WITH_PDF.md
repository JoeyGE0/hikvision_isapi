# Endpoint Comparison: Integration vs ISAPI PDF

## Summary of Differences Found

### ✅ CORRECT Endpoints (Match PDF)

1. **Image Adjustment**

   - **Integration:** `/ISAPI/Image/channels/{channel}/color`
   - **PDF:** `/ISAPI/Image/channels/<ID>/color` ✅
   - **Status:** ✅ CORRECT

2. **Two-way Audio**

   - **Integration:** `/ISAPI/System/TwoWayAudio/channels/{channel}`
   - **PDF:** `/ISAPI/System/TwoWayAudio/channels/<ID>` ✅
   - **Status:** ✅ CORRECT

3. **Supplement Light (Lights)**

   - **Integration:** `/ISAPI/Image/channels/{channel}/supplementLight`
   - **PDF:** `/ISAPI/Image/channels/<ID>/SupplementLight` (capital S)
   - **Status:** ⚠️ CASE DIFFERENCE (should work, but PDF shows capital S)

4. **IR Cut Filter**

   - **Integration:** `/ISAPI/Image/channels/{channel}/IrcutFilter`
   - **PDF:** `/ISAPI/Image/channels/<ID>/IrcutFilter` ✅
   - **Status:** ✅ CORRECT

5. **Audio Alarm**

   - **Integration:** `/ISAPI/Event/triggers/notifications/AudioAlarm?format=json`
   - **PDF:** `/ISAPI/Event/triggers/notifications/AudioAlarm?format=json` ✅
   - **Status:** ✅ CORRECT

6. **Line Detection**

   - **Integration:** `/ISAPI/Event/triggers/lineDetection`
   - **PDF Primary:** `/ISAPI/Event/triggers/<ID>` where `<ID>` = `linedetection` (lowercase)
   - **PDF Also Shows:** `lineDetection` (camelCase) for compatibility
   - **Status:** ⚠️ See "Potential Issues" section below

7. **Region Entrance**

   - **Integration:** `/ISAPI/Event/triggers/regionEntrance`
   - **PDF:** `/ISAPI/Event/triggers/<ID>` where `<ID>` = `regionEntrance` ✅
   - **Status:** ✅ CORRECT

8. **Region Exiting**

   - **Integration:** `/ISAPI/Event/triggers/regionExiting`
   - **PDF:** `/ISAPI/Event/triggers/<ID>` where `<ID>` = `regionExiting` ✅
   - **Status:** ✅ CORRECT

9. **Scene Change Detection**
   - **Integration:** `/ISAPI/Event/triggers/sceneChangeDetection`
   - **PDF:** `/ISAPI/Event/triggers/<ID>` where `<ID>` = `sceneChangeDetection` ✅
   - **Status:** ✅ CORRECT

### ⚠️ POTENTIAL ISSUES: Event Type IDs

1. **Intrusion Detection:**

   - **Integration:** `/ISAPI/Event/triggers/intrusionDetection`
   - **PDF Primary:** `/ISAPI/Event/triggers/fielddetection` (lowercase, one word)
   - **PDF Also Shows:** `fielddetection (fieldDetection)` - both formats supported for compatibility
   - **PDF Reference:** Line 42903-42905: "Intrusion Detection - fielddetection"
   - **Status:** ⚠️ **MISMATCH** - PDF primary format is `fielddetection`, integration uses `intrusionDetection`

2. **Line Detection:**
   - **Integration:** `/ISAPI/Event/triggers/lineDetection`
   - **PDF Primary:** `/ISAPI/Event/triggers/linedetection` (lowercase, one word)
   - **PDF Also Shows:** `linedetection (lineDetection)` - both formats supported for compatibility
   - **PDF Reference:** Line 42907-42909: "Line Crossing Detection - linedetection"
   - **Status:** ⚠️ **MISMATCH** - PDF primary format is `linedetection`, integration uses `lineDetection`

**Note:** The PDF shows both old (lowercase) and new (camelCase) formats for compatibility (lines 33493-33494, 33510-33511), but the primary/standard format in the event type table is lowercase. The integration should test both formats or use the lowercase primary format.

### 📋 Event Type IDs from PDF

According to the PDF (section 15.3.18), the `<ID>` in `/ISAPI/Event/triggers/<ID>` can be:

- `fielddetection` - Intrusion detection (NOT `intrusionDetection`)
- `lineDetection` - Line crossing detection
- `regionEntrance` - Region entrance detection
- `regionExiting` - Region exiting detection
- `sceneChangeDetection` - Sudden scene change detection
- `loitering` - Loitering detection
- `group` - People gathering detection
- `rapidMove` - Fast moving detection
- `parking` - Parking detection
- `unattendedBaggage` - Unattended baggage
- `attendedBaggage` - Object removal detection
- And many others...

### 🔍 Detection Method Differences

**Motion Detection & Tamper Detection:**

- **Integration:** Uses EventCap flags from capabilities XML (`isSupportMotionDetection`, `isSupportTamperDetection`)
- **PDF:** Confirms these flags exist in `XML_EventTriggersCap` (section 16.2.136)
- **Status:** ✅ CORRECT approach

**I/O Ports:**

- **Integration:** Uses IOCap counts from capabilities XML
- **PDF:** Confirms `IOCap/IOInputPortNums` and `IOCap/IOOutputPortNums` exist
- **Status:** ✅ CORRECT approach

## Recommendations

1. **Fix Intrusion Detection Endpoint:**

   - **Current:** `/ISAPI/Event/triggers/intrusionDetection`
   - **PDF Primary:** `/ISAPI/Event/triggers/fielddetection` (lowercase)
   - **Action:** Change to `fielddetection` OR test both and use whichever works
   - **Note:** PDF shows both `fielddetection` and `fieldDetection` for compatibility, but primary is lowercase

2. **Fix Line Detection Endpoint:**

   - **Current:** `/ISAPI/Event/triggers/lineDetection`
   - **PDF Primary:** `/ISAPI/Event/triggers/linedetection` (lowercase)
   - **Action:** Change to `linedetection` OR test both and use whichever works
   - **Note:** PDF shows both `linedetection` and `lineDetection` for compatibility, but primary is lowercase

3. **Supplement Light Case:**

   - **Current:** `supplementLight` (camelCase)
   - **PDF shows:** `SupplementLight` (PascalCase)
   - **Action:** Test if current works, if not, try `SupplementLight`

4. **Consider Testing Both Variants:**
   - For intrusion detection: test both `fielddetection` and `intrusionDetection`
   - For line detection: test both `linedetection` and `lineDetection`
   - Some cameras might support newer naming conventions, but PDF standard is lowercase

## PDF References

- **Image Color:** Section 15.4.6 (line 9493)
- **Two-way Audio:** Section 15.10.186 (line 22817)
- **Supplement Light:** Section 15.4.33 (line 10674)
- **IR Cut Filter:** Section 15.4.21 (line 10135)
- **Audio Alarm:** Section 15.3.21 (line 9042)
- **Event Triggers:** Section 15.3.18 (line 8868)
- **Event Type IDs:** Section showing event types (line 33500+)
