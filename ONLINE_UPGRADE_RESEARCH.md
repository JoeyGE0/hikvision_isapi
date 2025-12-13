# Hikvision Online Firmware Update Research

## Summary

The camera's firmware handles communication with Hikvision update servers internally. The integration only needs to call ISAPI endpoints - the camera does the actual server communication.

## ISAPI Endpoints

### 1. Check Capabilities

**Endpoint:** `GET /ISAPI/System/onlineUpgrade/capabilities`

**Response (XML):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<OnlineUpgradeCap version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<firmwareNum max="1"/>
<firmwareCode max="128"/>
<firmwareVersion max="64"/>
<firmwareCodeNumOnce max="1"/>
<upgradePercent min="0" max="100"/>
<UpgradePackageTask>
<isSupportDownloadStrategy>true</isSupportDownloadStrategy>
</UpgradePackageTask>
<rebootAfterUpgrade>manual</rebootAfterUpgrade>
</OnlineUpgradeCap>
```

**Purpose:** Check if the camera supports online upgrades and what features are available.

### 2. Get Online Upgrade Server Connection Status

**Endpoint:** `GET /ISAPI/System/onlineUpgrade/server`

**Response (XML):**
Returns `XML_OnlineUpgradeServer` with:

- `<connectStatus>` - Connection status to upgrade server (must be "true" to proceed)
- Server information (if available)

**Purpose:** Check if the device can connect to Hikvision's online upgrade servers. Only proceed to next steps if `connectStatus` is "true".

**Note:** This endpoint may reveal server URLs or connection details.

### 3. Get Available Firmware Version

**Endpoint:** `GET /ISAPI/System/onlineUpgrade/version`

**Response (when supported):**
Expected to return XML with:

- Available firmware version
- Changelog/release notes
- Download URL (if applicable)

**Response (when NOT supported - like this camera):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<statusCode>4</statusCode>
<statusString>Invalid Operation</statusString>
<subStatusCode>notSupport</subStatusCode>
<description>SW_ONLINE_UPGRADE_SUP not support.</description>
</ResponseStatus>
```

**Purpose:** Query Hikvision servers for available firmware updates. The camera firmware handles the actual HTTP request to Hikvision servers internally.

### 4. Set Device Online Upgrade Parameters (Optional)

**Endpoint:** `PUT /ISAPI/System/onlineUpgrade/deviceParameter?format=json`

**Purpose:** Configure device parameters for online upgrade (optional step).

### 5. Download Upgrade Package

**Endpoint:** `PUT /ISAPI/System/onlineUpgrade/downloadPackage?format=json`

**Purpose:** Initiate download of the upgrade package.

### 6. Get Download Progress

**Endpoint:** `GET /ISAPI/System/onlineUpgrade/downloadPackage/status?format=json`

**Purpose:** Monitor the progress of the upgrade package download.

### 7. Start Upgrade

**Endpoint:** `PUT /ISAPI/System/onlineUpgrade/upgradeWithoutDownload?format=json`

**Purpose:** Start the firmware upgrade process (after package is downloaded).

### 8. Get Upgrade Status

**Endpoint:** `GET /ISAPI/System/onlineUpgrade/status`

**Response (XML):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<OnlineUpgradeStatus version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<status>notUpgrade</status>
<percent>0</percent>
<taskID></taskID>
<packageName></packageName>
<statusDescription>0x0</statusDescription>
</OnlineUpgradeStatus>
```

**Purpose:** Check the current status of an ongoing or completed upgrade.

- `status`: Current upgrade status (e.g., "notUpgrade", "downloading", "upgrading", etc.)
- `percent`: Progress percentage (0-100)
- `taskID`: Task identifier
- `packageName`: Name of the upgrade package
- `statusDescription`: Status description code

## How It Works

1. **Camera-side communication:** When you call `/ISAPI/System/onlineUpgrade/version`, the camera firmware:

   - Makes an HTTP request to Hikvision's update servers (URLs are hardcoded in firmware)
   - Sends device information (model, current firmware version, serial number, etc.)
   - Receives response with available firmware info
   - Returns the result via ISAPI

2. **Integration-side:** We just need to:
   - Call `/ISAPI/System/onlineUpgrade/capabilities` to check support
   - Call `/ISAPI/System/onlineUpgrade/version` to get update info
   - Parse the XML response for version, changelog, etc.

## Device Information Used

From `/ISAPI/System/deviceInfo`, the camera likely sends:

- `model`: DS-2CD2387G3-LIS2UY/SL
- `firmwareVersion`: V5.8.10
- `serialNumber`: DS-2CD2387G3-LIS2UY/SL20250829AAWRGE8732853
- `deviceID`: 6bf40000-a940-11b4-833d-849459e4aa9d

## Server URLs (Not Discoverable)

The actual Hikvision server URLs are:

- **Hardcoded in the camera firmware** (not exposed via ISAPI)
- **Likely something like:** `update.hikvision.com` or `firmware.hikvision.com` or regional variants
- **Cannot be discovered** without:
  - Firmware reverse engineering
  - Network packet capture (when camera has internet access)
  - Hikvision official documentation

## Complete Programming Flow (from ISAPI Developer Guide)

Based on the official Hikvision ISAPI Developer Guide, the complete flow is:

1. **Check if device supports online upgrade:**

   - `GET /ISAPI/System/onlineUpgrade/capabilities`
   - Returns: `XML_OnlineUpgradeCap`

2. **Get connection status of online upgrade server:**

   - `GET /ISAPI/System/onlineUpgrade/server`
   - Returns: `XML_OnlineUpgradeServer`
   - **Important:** Only proceed if `<connectStatus>` is "true"

3. **Optional: Set device online upgrade parameters:**

   - `PUT /ISAPI/System/onlineUpgrade/deviceParameter?format=json`

4. **Get information of new upgrade package:**

   - `GET /ISAPI/System/onlineUpgrade/version`
   - Returns: Available firmware version, changelog, etc.

5. **Download upgrade package:**

   - `PUT /ISAPI/System/onlineUpgrade/downloadPackage?format=json`

6. **Get upgrade package download progress:**

   - `GET /ISAPI/System/onlineUpgrade/downloadPackage/status?format=json`

7. **Start upgrade when package is downloaded:**

   - `PUT /ISAPI/System/onlineUpgrade/upgradeWithoutDownload?format=json`

8. **Get upgrade status:**
   - `GET /ISAPI/System/onlineUpgrade/status`
   - Returns: Current upgrade status, progress percentage, etc.

## Implementation Notes

For the Home Assistant update entity (read-only, notification only):

1. Check `/ISAPI/System/onlineUpgrade/capabilities` first
2. Check `/ISAPI/System/onlineUpgrade/server` to verify server connection
3. If supported and connected, periodically call `/ISAPI/System/onlineUpgrade/version`
4. Parse XML response for:
   - `firmwareVersion` (latest available)
   - `firmwareCode` (firmware identifier)
   - `description` or similar (changelog/release notes)
5. Compare with current version from `/ISAPI/System/deviceInfo`
6. Display update available if versions differ
7. Optionally check `/ISAPI/System/onlineUpgrade/status` for any ongoing upgrades

## Current Camera Status

**This camera (DS-2CD2387G3-LIS2UY/SL):**

- ❌ Does NOT support online upgrades (`SW_ONLINE_UPGRADE_SUP not support`)
- ✅ Has online upgrade capabilities endpoint (returns structure)
- ✅ System capabilities show `isSupportOnlineUpgradeTask>true</isSupportOnlineUpgradeTask>` (but actual feature not supported)

## Related Endpoints

- `/ISAPI/System/upgradeFlag` - Upgrade flag/status
- `/ISAPI/System/deviceInfo` - Device information (current firmware version)
- `/ISAPI/System/autoMaintenance` - Auto maintenance settings
