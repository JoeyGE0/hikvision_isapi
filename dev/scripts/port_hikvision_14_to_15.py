#!/usr/bin/env python3
"""
Copy Hikvision ISAPI settings from camera SRC (default 192.168.1.14) to DST
(default 192.168.1.15). Does NOT copy device identity (no deviceInfo / users / network).

Preserves DST OSD label: <channelNameOverlay>...<name>...</name>

Run on a machine on the same LAN as the cameras:

  export HIK_PASS='your-admin-password'
  python3 port_hikvision_14_to_15.py

Optional: HIK_USER (default admin), HIK_SRC, HIK_DST.
"""
from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request


def opener(user: str, password: str, *host_ips: str) -> urllib.request.OpenerDirector:
    h = urllib.request.HTTPDigestAuthHandler()
    for ip in host_ips:
        h.add_password(None, f"http://{ip}", user, password)
    return urllib.request.build_opener(h)


def http_req(
    o: urllib.request.OpenerDirector,
    host: str,
    method: str,
    path: str,
    body: bytes | None = None,
    timeout: int = 45,
) -> tuple[int, str]:
    url = f"http://{host}{path}"
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/xml; charset=UTF-8")
    try:
        with o.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main() -> int:
    user = os.environ.get("HIK_USER", "admin")
    password = os.environ.get("HIK_PASS", "")
    if not password:
        print("Set HIK_PASS (camera admin password).", file=sys.stderr)
        return 1

    src = os.environ.get("HIK_SRC", "192.168.1.14")
    dst = os.environ.get("HIK_DST", "192.168.1.15")
    o = opener(user, password, src, dst)

    paths_put = [
        "/ISAPI/Streaming/channels/101",
        "/ISAPI/Streaming/channels/102",
        "/ISAPI/Streaming/channels/103",
        "/ISAPI/System/Video/inputs/channels/1/motionDetection",
        "/ISAPI/Image/channels/1",
        "/ISAPI/Image/channels/1/color",
        "/ISAPI/Image/channels/1/sharpness",
        "/ISAPI/System/Video/inputs/channels/1/privacyMask",
    ]

    print(f"SRC {src} -> DST {dst} (user {user})")

    code, ov_src = http_req(o, src, "GET", "/ISAPI/System/Video/inputs/channels/1/overlays")
    if code != 200:
        print(f"GET overlays SRC failed HTTP {code}\n{ov_src[:400]}", file=sys.stderr)
        return 1
    code, ov_dst = http_req(o, dst, "GET", "/ISAPI/System/Video/inputs/channels/1/overlays")
    if code != 200:
        print(f"GET overlays DST failed HTTP {code}\n{ov_dst[:400]}", file=sys.stderr)
        return 1

    m = re.search(
        r"(<channelNameOverlay[^>]*>.*?<name>)([^<]*)(</name>)",
        ov_dst,
        flags=re.DOTALL,
    )
    keep_name = m.group(2) if m else "Camera"
    ov_merged = re.sub(
        r"(<channelNameOverlay[^>]*>.*?<name>)([^<]*)(</name>)",
        lambda _m: f"{_m.group(1)}{keep_name}{_m.group(3)}",
        ov_src,
        count=1,
        flags=re.DOTALL,
    )
    code, resp = http_req(
        o, dst, "PUT", "/ISAPI/System/Video/inputs/channels/1/overlays", ov_merged.encode("utf-8")
    )
    print(f"PUT overlays HTTP {code}")
    if code not in (200, 201) or "<statusCode>1</statusCode>" not in resp:
        print(resp[:800])

    for path in paths_put:
        code, body = http_req(o, src, "GET", path)
        if code != 200:
            print(f"SKIP GET {path} on SRC -> HTTP {code}")
            continue
        if "ResponseStatus" in body and "statusCode>4" in body:
            print(f"SKIP {path} SRC error body")
            continue
        code2, resp2 = http_req(o, dst, "PUT", path, body.encode("utf-8"))
        ok = code2 in (200, 201) and (
            "<statusCode>1</statusCode>" in resp2 or not resp2.strip()
        )
        print(f"PUT {path} -> HTTP {code2} {'OK' if ok else 'CHECK'}")
        if not ok:
            print(resp2[:600])

    print("Done. If video looks wrong, reboot DST from the web UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
