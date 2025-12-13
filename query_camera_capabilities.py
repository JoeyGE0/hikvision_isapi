#!/usr/bin/env python3
"""Query Hikvision camera ISAPI capabilities and save all responses."""

import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
import json
from datetime import datetime
import sys

# Camera details - can be set via command line or here
CAMERA_IP = "192.168.1.13"  # Update this or pass as arg
USERNAME = "admin"  # Update this or pass as arg
PASSWORD = "PipSkye99!"  # Update this or pass as arg

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def query_endpoint(endpoint, auth):
    """Query an ISAPI endpoint and return XML as string."""
    url = f"http://{CAMERA_IP}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            return f"ERROR {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"

def main():
    global CAMERA_IP, USERNAME, PASSWORD
    
    # Allow command line args
    if len(sys.argv) >= 2:
        CAMERA_IP = sys.argv[1]
    if len(sys.argv) >= 3:
        USERNAME = sys.argv[2]
    if len(sys.argv) >= 4:
        PASSWORD = sys.argv[3]
    
    if not PASSWORD:
        print("ERROR: Please provide password!")
        print("Usage: python3 query_camera_capabilities.py [IP] [USERNAME] [PASSWORD]")
        print(f"  Example: python3 query_camera_capabilities.py 192.168.1.13 admin yourpassword")
        sys.exit(1)
    
    auth = HTTPDigestAuth(USERNAME, PASSWORD)
    
    # List of ISAPI endpoints to query
    endpoints = [
        # System info
        "/ISAPI/System/deviceInfo",
        "/ISAPI/System/capabilities",
        "/ISAPI/System/status",
        "/ISAPI/System/time",
        "/ISAPI/System/reboot",
        
        # Video/Image
        "/ISAPI/System/Video/inputs/channels",
        "/ISAPI/Image/channels/1",
        "/ISAPI/Image/channels/1/overlays",
        "/ISAPI/Image/channels/1/OSD",
        
        # Streaming
        "/ISAPI/Streaming/channels",
        "/ISAPI/Streaming/channels/1",
        
        # Smart features
        "/ISAPI/Smart/Image/channels/1",
        "/ISAPI/Smart/Image/channels/1/fieldDetection",
        "/ISAPI/Smart/Image/channels/1/lineDetection",
        "/ISAPI/Smart/Image/channels/1/sceneChangeDetection",
        "/ISAPI/Smart/Image/channels/1/regionEntrance",
        "/ISAPI/Smart/Image/channels/1/regionExiting",
        
        # Events
        "/ISAPI/Event/triggers",
        "/ISAPI/Event/channels/capabilities",
        "/ISAPI/Event/notification/httpHosts",
        
        # Motion/Tamper detection
        "/ISAPI/System/Video/inputs/channels/1/motionDetection",
        "/ISAPI/System/Video/inputs/channels/1/tamperDetection",
        "/ISAPI/System/Video/inputs/channels/1/videoLossDetection",
        "/ISAPI/System/Video/inputs/channels/1/sceneChangeDetection",
        "/ISAPI/System/Video/inputs/channels/1/fieldDetection",
        "/ISAPI/System/Video/inputs/channels/1/lineDetection",
        "/ISAPI/System/Video/inputs/channels/1/regionEntrance",
        "/ISAPI/System/Video/inputs/channels/1/regionExiting",
        
        # IO
        "/ISAPI/System/IO/inputs",
        "/ISAPI/System/IO/outputs",
        "/ISAPI/System/IO/inputs/1/status",
        "/ISAPI/System/IO/outputs/1/status",
        
        # Audio
        "/ISAPI/System/TwoWayAudio/channels",
        "/ISAPI/System/TwoWayAudio/channels/1",
        
        # Image settings
        "/ISAPI/Image/channels/1/supplementLight",
        "/ISAPI/Image/channels/1/whiteBalance",
        "/ISAPI/Image/channels/1/exposure",
        "/ISAPI/Image/channels/1/wideDynamicRange",
        "/ISAPI/Image/channels/1/backlight",
        "/ISAPI/Image/channels/1/brightness",
        "/ISAPI/Image/channels/1/color",
        "/ISAPI/Image/channels/1/defog",
        "/ISAPI/Image/channels/1/ircutFilter",
        
        # Security
        "/ISAPI/Security/users",
        "/ISAPI/Security/adminAccesses",
        
        # Storage
        "/ISAPI/ContentMgmt/Storage",
        
        # Holidays
        "/ISAPI/System/Holidays",
        
        # Online upgrade
        "/ISAPI/System/onlineUpgrade/capabilities",
        "/ISAPI/System/onlineUpgrade/version",
    ]
    
    results = {}
    print(f"Querying {len(endpoints)} endpoints from {CAMERA_IP}...")
    print("=" * 80)
    
    for endpoint in endpoints:
        print(f"Querying: {endpoint}")
        result = query_endpoint(endpoint, auth)
        results[endpoint] = result
        if result.startswith("ERROR") or result.startswith("EXCEPTION"):
            print(f"  ❌ {result[:100]}")
        else:
            print(f"  ✅ Success ({len(result)} bytes)")
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"camera_capabilities_{CAMERA_IP.replace('.', '_')}_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 80)
    print(f"Results saved to: {filename}")
    print(f"\nSummary:")
    print(f"  Total endpoints: {len(endpoints)}")
    successful = sum(1 for v in results.values() if not (v.startswith("ERROR") or v.startswith("EXCEPTION")))
    print(f"  Successful: {successful}")
    print(f"  Failed: {len(endpoints) - successful}")
    
    # Pretty print capabilities
    if "/ISAPI/System/capabilities" in results:
        cap_result = results["/ISAPI/System/capabilities"]
        if not (cap_result.startswith("ERROR") or cap_result.startswith("EXCEPTION")):
            print("\n" + "=" * 80)
            print("CAPABILITIES XML:")
            print("=" * 80)
            try:
                root = ET.fromstring(cap_result)
                ET.indent(root, space="  ")
                print(ET.tostring(root, encoding='unicode'))
            except:
                print(cap_result[:2000])

if __name__ == "__main__":
    main()

