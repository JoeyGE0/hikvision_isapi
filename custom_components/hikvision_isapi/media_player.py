#!/usr/bin/env python3
"""Test script to play audio files via Hikvision ISAPI two-way audio."""
import sys
import requests
import xml.etree.ElementTree as ET
import time
import io
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Camera config
HOST = "192.168.1.13"
USERNAME = "admin"
PASSWORD = "PipSkye99!"

XML_NS = "{http://www.hikvision.com/ver20/XMLSchema}"

def get_two_way_audio():
    """Get current two-way audio settings."""
    try:
        url = f"http://{HOST}/ISAPI/System/TwoWayAudio/channels/1"
        response = requests.get(
            url,
            auth=(USERNAME, PASSWORD),
            verify=False,
            timeout=5
        )
        response.raise_for_status()
        xml = ET.fromstring(response.text)
        
        enabled = xml.find(f".//{XML_NS}enabled")
        compression = xml.find(f".//{XML_NS}audioCompressionType")
        speaker_vol = xml.find(f".//{XML_NS}speakerVolume")
        
        return {
            "enabled": enabled.text.strip().lower() == "true" if enabled is not None else False,
            "compression": compression.text.strip() if compression is not None else None,
            "speakerVolume": int(speaker_vol.text.strip()) if speaker_vol is not None else None,
        }
    except Exception as e:
        print(f"Error getting two-way audio: {e}")
        return None

def enable_two_way_audio():
    """Enable two-way audio channel."""
    try:
        audio_data = get_two_way_audio()
        if not audio_data:
            print("Failed to get current audio settings")
            return False
        
        compression = audio_data.get('compression', 'G.711ulaw')
        speaker_vol = audio_data.get('speakerVolume', 100)
        
        xml_data = f"""<TwoWayAudioChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<enabled>true</enabled>
<audioCompressionType>{compression}</audioCompressionType>
<speakerVolume>{speaker_vol}</speakerVolume>
<microphoneVolume>100</microphoneVolume>
<noisereduce>true</noisereduce>
<audioInputType>MicIn</audioInputType>
<audioOutputType>Speaker</audioOutputType>
</TwoWayAudioChannel>"""
        
        url = f"http://{HOST}/ISAPI/System/TwoWayAudio/channels/1"
        response = requests.put(
            url,
            auth=(USERNAME, PASSWORD),
            data=xml_data,
            headers={"Content-Type": "application/xml"},
            verify=False,
            timeout=5
        )
        response.raise_for_status()
        print(f"✓ Two-way audio enabled (compression: {compression}, volume: {speaker_vol}%)")
        return True
    except Exception as e:
        print(f"✗ Failed to enable two-way audio: {e}")
        return False

def open_audio_session():
    """Open two-way audio session. Returns sessionId."""
    try:
        url = f"http://{HOST}/ISAPI/System/TwoWayAudio/channels/1/open"
        response = requests.put(
            url,
            auth=(USERNAME, PASSWORD),
            verify=False,
            timeout=5
        )
        response.raise_for_status()
        xml = ET.fromstring(response.text)
        session_id = xml.find(f".//{XML_NS}sessionId")
        if session_id is not None:
            sid = session_id.text.strip()
            print(f"✓ Audio session opened: {sid}")
            return sid
        else:
            print("✗ No sessionId in response")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Failed to open audio session: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def close_audio_session():
    """Close two-way audio session."""
    try:
        url = f"http://{HOST}/ISAPI/System/TwoWayAudio/channels/1/close"
        response = requests.put(
            url,
            auth=(USERNAME, PASSWORD),
            verify=False,
            timeout=5
        )
        response.raise_for_status()
        print("✓ Audio session closed")
        return True
    except Exception as e:
        print(f"✗ Failed to close audio session: {e}")
        return False

def send_audio_data(audio_data: bytes, session_id: str = None):
    """Send audio data to camera.
    
    Args:
        audio_data: Raw audio bytes (should be G.711ulaw, 8000Hz, mono)
        session_id: Optional session ID (some cameras don't require it)
    """
    endpoint = f"http://{HOST}/ISAPI/System/TwoWayAudio/channels/1/audioData"
    
    # Chunk size: 160 bytes = 20ms of audio at 8kHz
    # G.711ulaw: 1 byte per sample, 8000 samples/sec = 8000 bytes/sec
    chunk_size = 160
    sleep_time = 0.02  # 20ms delay to maintain 8000 bytes/sec rate
    
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    session.verify = False
    
    total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
    print(f"Streaming {len(audio_data)} bytes in {total_chunks} chunks ({len(audio_data) / 8000.0:.2f} seconds of audio)")
    
    sent_bytes = 0
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i + chunk_size]
        
        # Pad chunk to exact size if needed
        if len(chunk) < chunk_size:
            chunk = chunk + (b'\x7F' * (chunk_size - len(chunk)))  # 0x7F is silence in ulaw
        
        try:
            response = session.put(
                endpoint,
                data=chunk,
                timeout=0.3,
                stream=True
            )
            sent_bytes += len(chunk)
            
            # Log progress every second (50 chunks)
            if (i // chunk_size) % 50 == 0 and i > 0:
                print(f"  Progress: {sent_bytes}/{len(audio_data)} bytes ({(sent_bytes / len(audio_data)) * 100:.1f}%)")
            
            time.sleep(sleep_time)
            
        except requests.exceptions.Timeout:
            # Timeout is OK - camera is processing
            sent_bytes += len(chunk)
            time.sleep(sleep_time)
            continue
        except Exception as e:
            print(f"  Warning: Error sending chunk at {sent_bytes} bytes: {e}")
            sent_bytes += len(chunk)
            time.sleep(sleep_time)
    
    print(f"✓ Audio streaming complete: sent {sent_bytes}/{len(audio_data)} bytes")
    session.close()

def generate_test_tone(duration_seconds: float = 1.0, frequency: int = 440):
    """Generate a simple test tone in G.711ulaw format.
    
    This generates a sine wave at the specified frequency.
    Note: This is a basic implementation - for real audio files, use ffmpeg/pydub.
    """
    import math
    import struct
    
    sample_rate = 8000
    num_samples = int(sample_rate * duration_seconds)
    ulaw_data = bytearray()
    
    # Generate sine wave samples
    for i in range(num_samples):
        t = i / sample_rate
        # Generate sine wave (-1.0 to 1.0)
        sample = math.sin(2 * math.pi * frequency * t)
        # Convert to 16-bit PCM (-32768 to 32767)
        pcm_sample = int(sample * 32767)
        # Convert to ulaw (simplified - using audioop would be better)
        # For now, we'll use a basic approximation
        ulaw_byte = _linear_to_ulaw(pcm_sample)
        ulaw_data.append(ulaw_byte)
    
    return bytes(ulaw_data)

def _linear_to_ulaw(linear: int) -> int:
    """Convert 16-bit linear PCM to 8-bit ulaw (simplified version)."""
    # Clamp to 16-bit range
    linear = max(-32768, min(32767, linear))
    
    # Get sign
    sign = 0 if linear >= 0 else 0x80
    linear = abs(linear)
    
    # Find exponent (0-7)
    exp = 0
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
    
    # Mantissa (4 bits)
    mantissa = (linear >> (exp + 3)) & 0x0F
    
    # Combine: sign (1) + exponent (3) + mantissa (4)
    ulaw = sign | (exp << 4) | mantissa
    
    # Invert all bits for ulaw
    return (~ulaw) & 0xFF

def main():
    """Main test function."""
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        print(f"Loading audio file: {audio_file}")
        try:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
            print(f"Loaded {len(audio_data)} bytes")
            print("Note: File should be in G.711ulaw format, 8000Hz, mono")
            print("If not, convert with: ffmpeg -i input.wav -ar 8000 -ac 1 -acodec pcm_mulaw output.ulaw")
        except Exception as e:
            print(f"✗ Failed to load audio file: {e}")
            return
    else:
        print("Generating test tone (440Hz, 1 second)...")
        audio_data = generate_test_tone(1.0, 440)
        print(f"Generated {len(audio_data)} bytes of test tone")
    
    print("\n" + "="*60)
    print("Step 1: Enable two-way audio")
    print("="*60)
    if not enable_two_way_audio():
        print("Failed to enable two-way audio. Aborting.")
        return
    
    print("\n" + "="*60)
    print("Step 2: Open audio session (optional)")
    print("="*60)
    session_id = open_audio_session()
    if not session_id:
        print("Note: Session open failed, but some cameras don't require it. Continuing...")
    
    print("\n" + "="*60)
    print("Step 3: Send audio data")
    print("="*60)
    try:
        send_audio_data(audio_data, session_id)
    except Exception as e:
        print(f"✗ Error sending audio: {e}")
    
    print("\n" + "="*60)
    print("Step 4: Close audio session")
    print("="*60)
    close_audio_session()
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)

if __name__ == "__main__":
    main()

