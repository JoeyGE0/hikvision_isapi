# Audio Conversion Research - G.711ulaw Converter

## Overview

Research on how g711.org works and how to implement an in-built audio converter for the Hikvision ISAPI integration, allowing users to play any audio file (sound effects, songs, etc.) without pre-conversion.

## How g711.org Works

Based on research, g711.org is a web-based audio converter that:

1. **Accepts various input formats**: DRM-free media files up to 50MB
2. **Converts to telephony formats**: Including G.711ulaw WAV (8kHz, Mono, CCITT μ-law)
3. **Features**:
   - Volume adjustment (Quiet, Lower, Medium, High, Maximum)
   - Audio optimization for phone systems (bandpass filter)
   - Multiple output formats (μ-law, A-law, PCM variants, G.722, G.729, RAW)

**Conversion Process** (inferred):
1. Decode input audio (MP3, WAV, etc.) to linear PCM
2. Resample to 8kHz (if needed)
3. Convert to mono (if stereo)
4. Apply volume adjustment
5. Optionally apply bandpass filter for phone optimization
6. Encode to G.711ulaw
7. Wrap in WAV container with proper headers

## G.711ulaw Encoding Algorithm

G.711 is an ITU-T standard for audio companding used in telephony:
- **Sample Rate**: 8kHz (standard for telephony)
- **Bit Depth**: 8 bits per sample
- **Channels**: Mono (1 channel)
- **Bitrate**: 64 kbps
- **Algorithm**: Logarithmic companding (μ-law for North America/Japan, A-law for Europe)

### μ-law Encoding Formula

The μ-law algorithm compresses 16-bit linear PCM to 8-bit logarithmic:
1. Take absolute value and determine sign bit
2. Find exponent (0-7) based on magnitude ranges
3. Extract mantissa (4 bits) from the sample
4. Combine: sign (1 bit) + exponent (3 bits) + mantissa (4 bits) = 8 bits
5. Invert all bits (ones' complement)

### Existing Implementation in Codebase

Found in `api.py` `play_test_tone()` method (lines 1369-1398):

```python
def linear_to_ulaw(linear):
    linear = max(-32768, min(32767, linear))  # Clamp to 16-bit range
    sign = 0 if linear >= 0 else 0x80
    linear = abs(linear)
    exp = 0
    # Find exponent based on magnitude ranges
    if linear >= 256:
        if linear >= 1024:
            if linear >= 4096:
                if linear >= 16384:
                    exp = 7
                else:
                    exp = 6
            else:
                exp = 5
        else:
            exp = 4
    else:
        if linear >= 16:
            if linear >= 64:
                exp = 3
            else:
                exp = 2
        else:
            if linear >= 4:
                exp = 1
            else:
                exp = 0
    mantissa = (linear >> (exp + 3)) & 0x0F
    ulaw = sign | (exp << 4) | mantissa
    return (~ulaw) & 0xFF  # Invert all bits
```

**Note**: This is a custom implementation. Should verify against standard G.711ulaw spec.

## Implementation Approaches

### Option 1: Python-based (Server-side in Home Assistant)

**Libraries Available**:
- `pydub` + `ffmpeg`: Can decode any format, resample, convert to mono
- `audioop`: Python standard library for audio operations (has `lin2ulaw` function!)
- `wave`: For creating WAV files

**Process**:
1. Use `pydub` to load audio file (supports MP3, WAV, etc.)
2. Resample to 8kHz: `audio = audio.set_frame_rate(8000)`
3. Convert to mono: `audio = audio.set_channels(1)`
4. Get raw PCM samples: `raw_audio = audio.raw_data`
5. Convert to G.711ulaw: Use `audioop.lin2ulaw()` (standard library!)
6. Create WAV file with G.711ulaw format code (0x0007)

**Advantages**:
- Can handle any audio format (via ffmpeg)
- Runs on Home Assistant server
- Can process large files
- Standard library functions available

**Disadvantages**:
- Requires `ffmpeg` dependency
- Server-side processing (uses resources)
- May be slower for large files

### Option 2: Web Audio API (Client-side in Home Assistant UI)

**Process**:
1. Use `AudioContext` to decode audio file
2. Use `OfflineAudioContext` to resample to 8kHz
3. Convert stereo to mono (average channels)
4. Get `AudioBuffer` with 8kHz mono PCM
5. Convert each sample to G.711ulaw using JavaScript implementation
6. Create WAV file with proper headers
7. Download or send to Home Assistant

**Advantages**:
- No server resources used
- Fast (client-side processing)
- Works in browser

**Disadvantages**:
- Limited to browser-supported formats
- May have memory limits for large files
- Requires JavaScript G.711ulaw encoder implementation

### Option 3: Hybrid Approach

- **Small files (< 5MB)**: Use Web Audio API (client-side)
- **Large files or unsupported formats**: Use Python/ffmpeg (server-side)
- **Both**: Provide UI in Home Assistant to upload and convert

## Required Conversion Steps

For any input audio file:

1. **Decode** to linear PCM (16-bit or 32-bit float)
2. **Resample** to 8kHz (if not already)
3. **Convert to mono** (if stereo - average channels or take left channel)
4. **Normalize/Adjust volume** (optional, based on user preference)
5. **Apply bandpass filter** (optional, for phone optimization: ~300Hz - 3400Hz)
6. **Encode to G.711ulaw** using μ-law algorithm
7. **Wrap in WAV container**:
   - RIFF header
   - fmt chunk (format code 0x0007 for G.711ulaw)
   - data chunk with ulaw bytes

## Python Implementation Example (Using Standard Library)

```python
import wave
import audioop
from pydub import AudioSegment

def convert_to_ulaw_wav(input_file: str, output_file: str, volume_adjust: float = 1.0):
    """Convert any audio file to G.711ulaw WAV format."""
    # Load and process audio
    audio = AudioSegment.from_file(input_file)
    
    # Resample to 8kHz
    audio = audio.set_frame_rate(8000)
    
    # Convert to mono
    audio = audio.set_channels(1)
    
    # Adjust volume (if needed)
    if volume_adjust != 1.0:
        audio = audio + (20 * math.log10(volume_adjust))  # dB adjustment
    
    # Get raw 16-bit PCM data
    raw_pcm = audio.raw_data
    
    # Convert to G.711ulaw using standard library
    ulaw_data = audioop.lin2ulaw(raw_pcm, 2)  # 2 = 16-bit samples
    
    # Create WAV file with G.711ulaw format
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(1)  # 8-bit (ulaw)
        wav_file.setframerate(8000)  # 8kHz
        wav_file.setcomptype('ULAW', 'CCITT G.711 u-law')  # G.711ulaw
        wav_file.writeframes(ulaw_data)
```

## JavaScript Implementation Example (Web Audio API)

```javascript
async function convertToUlawWav(audioFile) {
    // Decode audio
    const arrayBuffer = await audioFile.arrayBuffer();
    const audioContext = new AudioContext();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    
    // Resample to 8kHz using OfflineAudioContext
    const offlineContext = new OfflineAudioContext(1, audioBuffer.duration * 8000, 8000);
    const source = offlineContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineContext.destination);
    source.start();
    const resampledBuffer = await offlineContext.startRendering();
    
    // Convert to mono (already mono from OfflineAudioContext with 1 channel)
    const samples = resampledBuffer.getChannelData(0);
    
    // Convert to G.711ulaw
    const ulawData = new Uint8Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const pcmSample = Math.max(-1, Math.min(1, samples[i]));
        const linear = Math.floor(pcmSample * 32767);
        ulawData[i] = linearToUlaw(linear);
    }
    
    // Create WAV file
    return createUlawWavFile(ulawData, 8000);
}
```

## Recommendations

1. **Use Python approach** (Option 1) for Home Assistant integration:
   - Leverage `audioop.lin2ulaw()` from standard library (proven, correct)
   - Use `pydub` for format support (requires ffmpeg)
   - Can be integrated as a service or helper function

2. **Add conversion service**:
   - `hikvision_isapi.convert_audio` service
   - Input: media file path or URL
   - Output: G.711ulaw WAV file in `/config/www/` or media source
   - Options: volume adjustment, bandpass filter

3. **Integration points**:
   - Media player can auto-convert on-the-fly (cache converted files)
   - Or provide UI to convert files before playing
   - Store converted files in media source for reuse

4. **Verify existing `linear_to_ulaw` function**:
   - Compare with `audioop.lin2ulaw()` from Python standard library
   - May want to replace custom implementation with standard library version

## Next Steps

1. Test `audioop.lin2ulaw()` vs existing `linear_to_ulaw()` function
2. Implement Python-based converter using `pydub` + `audioop`
3. Add conversion service to integration
4. Integrate with media player (auto-convert or manual conversion)
5. Add UI for file upload and conversion (optional)

## References

- G.711 ITU-T Standard: Logarithmic companding algorithm
- Python `audioop` module: `lin2ulaw()` function (standard library)
- `pydub`: Audio manipulation library (requires ffmpeg)
- Web Audio API: Browser-based audio processing
- g711.org: Reference implementation (web-based converter)

