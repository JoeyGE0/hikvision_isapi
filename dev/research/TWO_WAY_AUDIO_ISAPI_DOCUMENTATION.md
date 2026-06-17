# Two-Way Audio ISAPI Documentation

## Source

Intelligent Security API (General Application) Developer Guide - Pages 83, 355-360

## Programming Flow (Page 83)

The two-way audio flow follows this sequence:

1. **Optional:** Get parameters of all two-way audio channels

   - `GET /ISAPI/System/TwoWayAudio/channels`
   - Returns channel configuration (ID, encoding mode, etc.)

2. **Start two-way audio of a channel**

   - `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/open`
   - Opens an audio session and returns `sessionId`

3. **Transmit audio data** (can be done simultaneously):

   - **Send Audio Data to Device:** `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/audioData`
   - **Receive Audio Data from Device:** `GET /ISAPI/System/TwoWayAudio/channels/<ID>/audioData`

4. **Stop two-way audio**
   - `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/close`

## Endpoint Details

### 15.10.185 GET /ISAPI/System/TwoWayAudio/channels (Page 355)

**Purpose:** Get audio parameters of all two-way audio channels

**Method:** `GET`

**Query:** None

**Request:** None

**Response:**

- Succeeded: `XML_TwoWayAudioChannelList`
- Failed: `XML_ResponseStatus`

---

### 15.10.186 GET/PUT /ISAPI/System/TwoWayAudio/channels/<ID> (Page 356)

**Purpose:** Get or set parameters of a specific two-way audio channel

**GET Method:**

- **Description:** Get the parameters of a specific two-way audio channel
- **Query:** None
- **Request:** None
- **Response:**
  - Succeeded: `XML_TwoWayAudioChannel`
  - Failed: `XML_ResponseStatus`

**PUT Method:**

- **Description:** Set the parameters of a specific two-way audio channel
- **Query:** None
- **Request:** `XML_TwoWayAudioChannel`
- **Response:** `XML_ResponseStatus`

**Example XML Structure:**

```xml
<TwoWayAudioChannel version="2.0" xmlns="http://www.isapi.com/ver20/XMLSchema">
    <id>1</id>
    <enabled>false</enabled>
    <audioCompressionType>G.711ulaw</audioCompressionType>
    <audioInputType>MicIn</audioInputType>
    <speakerVolume>50</speakerVolume>
    <noisereduce>false</noisereduce>
</TwoWayAudioChannel>
```

---

### 15.10.187 GET/PUT /ISAPI/System/TwoWayAudio/channels/<ID>/audioData (Page 357)

**Purpose:** Receive or send audio data from or to a specific two-way audio channel

**GET Method (Table 15-612):**

- **Description:** Receive audio data from a specific two-way audio channel
- **Query:**
  - `sessionId`: Communication session ID
    - **Required when:** Two-way audio is started between multiple channels and a channel
    - **Not required when:** Single channel scenario (optional)
- **Request:** None
- **Response:**
  - Succeeded: Audio data
  - Failed: `XML_ResponseStatus`
- **Content-Type (Response):** `audio/basic`

**PUT Method (Table 15-613):**

- **Description:** Send audio data to a specific two-way audio channel
- **Query:**
  - `sessionId`: Communication session ID
    - **Required when:** Two-way audio is started between multiple channels and a channel
    - **Not required when:** Single channel scenario (optional)
- **Request:** Audio data (binary)
- **Response:** `XML_ResponseStatus`
- **Content-Type (Request):** `application/octet-stream`

**Remarks:**

- The `<ID>` in the request URL refers to the two-way audio channel ID

**Example PUT Request (Page 357):**

```
PUT /ISAPI/System/TwoWayAudio/channels/1/audioData HTTP/1.1
Host: 10.17.132.49
Authorization: Digest username="admin", realm="...", nonce="...", uri="/ISAPI/System/TwoWayAudio/channels/1/audioData", response="..."
Connection: keep-alive
Content-Length: <audio_data_length>
Content-Type: application/octet-stream

<binary audio data>
```

**Example GET Response (Page 358):**

```
HTTP/1.1 200 OK
Content-Type: audio/basic

<binary audio data>
```

---

### 15.10.188 GET /ISAPI/System/TwoWayAudio/channels/<ID>/capabilities (Page 358)

**Purpose:** Get the capability of a specific two-way audio channel

**Method:** `GET`

**Query:** None

**Request:** None

**Response:**

- Succeeded: `XML_TwoWayAudioChannelCap`
- Failed: `XML_ResponseStatus`

---

### 15.10.189 PUT /ISAPI/System/TwoWayAudio/channels/<ID>/close (Page 359)

**Purpose:** Stop two-way audio of a specific channel

**Method:** `PUT`

**Query:** None

**Request:** None (Content-Length: 0)

**Response:** `XML_ResponseStatus`

**Example Request:**

```
PUT /ISAPI/System/TwoWayAudio/channels/1/close HTTP/1.1
Host: 10.17.132.49
Authorization: Digest username="admin", realm="...", nonce="...", uri="/ISAPI/System/TwoWayAudio/channels/1/close", response="..."
Content-Length: 0
```

**Example Response:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ResponseStatus version="2.0" xmlns="http://www.isapi.com/ver20/XMLSchema">
    <requestURL>/ISAPI/System/TwoWayAudio/channels/1/close</requestURL>
    <statusCode>1</statusCode>
    <statusString>OK</statusString>
    <subStatusCode>ok</subStatusCode>
</ResponseStatus>
```

---

### 15.10.190 PUT /ISAPI/System/TwoWayAudio/channels/<ID>/open (Page 360)

**Purpose:** Start two-way audio of a specific channel

**Method:** `PUT`

**Query:** None

**Request:** None (Content-Length: 0)

**Response:**

- Succeeded: `XML_TwoWayAudioSession`
- Failed: `XML_ResponseStatus`

**Example Request:**

```
PUT /ISAPI/System/TwoWayAudio/channels/1/open HTTP/1.1
Host: 10.17.132.49
Authorization: Digest username="admin", realm="DS-2CD2F12FWD-IWS", nonce="4e3055314e6a64434e7a59365a4445304f5456685957453d", uri="/ISAPI/System/TwoWayAudio/channels/1/open", response="368dda22535b9783bdccafc3b2ded29a"
Content-Length: 0
```

**Example Response:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<TwoWayAudioSession version="2.0" xmlns="http://www.isapi.com/ver20/XMLSchema">
    <sessionId>2093716360</sessionId>
</TwoWayAudioSession>
```

## Key Findings

### SessionId Usage

1. **Obtained from `/open` endpoint:**

   - The `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/open` endpoint returns an `XML_TwoWayAudioSession` containing a `<sessionId>` element
   - Example: `<sessionId>2093716360</sessionId>`

2. **Used as query parameter in `/audioData` endpoint:**

   - Format: `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/audioData?sessionId=<sessionId>`
   - **Required when:** Two-way audio is started between multiple channels and a channel
   - **Optional when:** Single channel scenario (but should be included for consistency)

3. **Not used in `/close` endpoint:**
   - The close endpoint does not require or use the sessionId
   - Simply: `PUT /ISAPI/System/TwoWayAudio/channels/<ID>/close`

### Content-Type Headers

- **Sending audio (PUT /audioData):** `Content-Type: application/octet-stream`
- **Receiving audio (GET /audioData response):** `Content-Type: audio/basic`
- **Channel configuration (PUT /channels/<ID>):** `Content-Type: application/xml`
- **Open/Close endpoints:** No Content-Type header needed (Content-Length: 0)

### Audio Format

- **Codec:** G.711ulaw (as specified in channel configuration)
- **Sample Rate:** 8000 Hz (standard for G.711ulaw)
- **Channels:** Mono (1 channel)
- **Data Format:** Raw binary audio data (not WAV container when streaming)

### Important Notes

1. The `<ID>` in all endpoints refers to the **two-way audio channel ID**, not a session ID
2. The sessionId is returned from the `/open` endpoint and should be used as a query parameter when sending/receiving audio data
3. For single-channel scenarios, sessionId may be optional, but it's recommended to always include it for consistency
4. The audio data should be sent as raw binary (application/octet-stream), not in a container format
5. The camera manages the session internally after opening, so the sessionId links the audio data to the correct session

## Implementation Notes

### Current Implementation Status

✅ **Fixed Issues:**

- Added `sessionId` as query parameter to `PUT /audioData` requests
- Added `Content-Type: application/octet-stream` header for audio data
- Properly extract `sessionId` from `/open` response XML

### Recommended Flow

1. Enable two-way audio channel: `PUT /ISAPI/System/TwoWayAudio/channels/1` (with enabled=true)
2. Open session: `PUT /ISAPI/System/TwoWayAudio/channels/1/open` → Extract `sessionId`
3. Send audio data: `PUT /ISAPI/System/TwoWayAudio/channels/1/audioData?sessionId=<sessionId>` (with binary audio data)
4. Close session: `PUT /ISAPI/System/TwoWayAudio/channels/1/close`

### Chunked Streaming

- Audio should be sent in chunks to maintain proper playback rate
- For G.711ulaw at 8kHz: 8000 bytes/second
- Recommended chunk size: 160 bytes = 20ms of audio
- Delay between chunks: 20ms to maintain proper playback speed
