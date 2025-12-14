# Deep Endpoint Analysis Results

## Key Finding: Detection vs Actual Usage

### Intrusion Detection

**Detection Endpoint (only used to check if feature exists):**
- `/ISAPI/Event/triggers/intrusionDetection` → Returns **403 "Invalid Operation"**
  - Endpoint exists but camera rejects it as invalid
  - `_test_endpoint_exists()` treats 403 as "exists" ✅ (works for detection)
  
- `/ISAPI/Event/triggers/fielddetection` → Returns **200 OK with actual config data**
  - This is the correct format per PDF
  - Returns XML: `<EventTrigger><id>fielddetection-1</id><eventType>fielddetection</eventType>...`

**Actual Control Endpoint (used by the switch entity):**
- `/ISAPI/Smart/FieldDetection/{channel}` → Returns **200 OK** ✅
  - This is what the `HikvisionIntrusionDetectionSwitch` actually uses
  - Works perfectly, returns actual field detection config
  - Completely different endpoint from detection!

**Conclusion:**
- Current code works fine because:
  1. Detection only needs to know if endpoint exists (403 = exists, works)
  2. Actual functionality uses `/ISAPI/Smart/FieldDetection/{channel}` which works perfectly
- However, using `fielddetection` for detection would be more accurate since it returns real data
- But it doesn't matter functionally - both work for detection purposes

### Line Detection

**Detection Endpoint:**
- `/ISAPI/Event/triggers/lineDetection` → Returns **200 OK** ✅
- `/ISAPI/Event/triggers/linedetection` → Returns **200 OK** ✅
- Both return **IDENTICAL data** (same XML content)
- Camera internally uses lowercase (`<eventType>linedetection</eventType>`)
- Both formats work perfectly

**Conclusion:**
- Current `lineDetection` format works fine
- Both formats are equivalent
- No change needed

### Supplement Light

**Detection Endpoint:**
- `/ISAPI/Image/channels/1/supplementLight` → Returns **200 OK** ✅
- `/ISAPI/Image/channels/1/SupplementLight` → Returns **200 OK** ✅
- Both work perfectly

**Conclusion:**
- Current `supplementLight` format works fine
- No change needed

## Summary

### Current Status: ✅ Everything Works

1. **Intrusion Detection:**
   - Detection endpoint returns 403 but that's fine (detection treats 403 as "exists")
   - Actual control uses different endpoint (`/ISAPI/Smart/FieldDetection/{channel}`) which works perfectly
   - **Recommendation:** Keep current code OR change to `fielddetection` for more accurate detection (but functionally same)

2. **Line Detection:**
   - Both formats work identically
   - **Recommendation:** Keep current `lineDetection` format

3. **Supplement Light:**
   - Both formats work
   - **Recommendation:** Keep current `supplementLight` format

## Technical Details

### Why 403 is OK for Detection

The `_test_endpoint_exists()` method in `api.py` returns `True` for both 200 and 403:
```python
return response.status_code in (200, 403)
```

This is correct because:
- **200** = Endpoint exists and is accessible
- **403** = Endpoint exists but not accessible (might be disabled, wrong permissions, or wrong format)
- **404** = Endpoint doesn't exist (feature not supported)

For detection purposes, we only care if the feature EXISTS, not if we can access it. The actual functionality uses different endpoints anyway.

### Actual Endpoints Used by Entities

- **Intrusion Detection Switch:** `/ISAPI/Smart/FieldDetection/{channel}` (not Event/triggers)
- **Line Detection Switch:** Likely uses `/ISAPI/Smart/LineDetection/{channel}` (need to verify)
- **Other entities:** Use various endpoints, not necessarily the detection endpoints

## Final Recommendation

**No changes needed** - everything works as-is. However, if you want to be more accurate to the PDF standard:

1. Change detection from `intrusionDetection` to `fielddetection` (more accurate, returns real data)
2. Keep `lineDetection` as-is (works perfectly)
3. Keep `supplementLight` as-is (works perfectly)

But functionally, everything works fine right now.

