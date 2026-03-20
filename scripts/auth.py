#!/usr/bin/env python3
"""
Jike QR Authentication (standalone)
Run directly: python3 scripts/auth.py
No pip install required — only needs `requests`.

Author: Claude Opus 4.5
"""

import json
import sys
import time
import urllib.parse
from typing import Optional

import requests

API_BASE = "https://api.ruguoapp.com"
HEADERS = {
    "Origin": "https://web.okjike.com",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "DNT": "1",
}


def create_session() -> str:
    resp = requests.post(
        f"{API_BASE}/sessions.create",
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()["uuid"]


def build_qr_payload(uuid: str) -> str:
    scan_url = f"https://www.okjike.com/account/scan?uuid={uuid}"
    return (
        "jike://page.jk/web?url="
        + urllib.parse.quote(scan_url, safe="")
        + "&displayHeader=false&displayFooter=false"
    )


def render_qr(data: str, uuid: str) -> bool:
    """Render QR code both as ASCII and HTML file for better UX."""
    try:
        import qrcode
        import base64
        from io import BytesIO

        # Generate QR image
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        # Save to buffer and encode as base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Create HTML file with embedded QR
        html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>即刻二维码登录</title></head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;font-family:sans-serif;">
<div style="background:white;padding:30px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);text-align:center;">
<h2 style="color:#333;margin-bottom:20px;">即刻登录</h2>
<img src="data:image/png;base64,{img_base64}" alt="QR Code" style="width:300px;height:300px;">
<p style="color:#666;margin-top:20px;">请使用即刻 App 扫描二维码</p>
<p style="color:#999;font-size:12px;margin-top:15px;">Session: {uuid}</p>
</div>
</body>
</html>'''

        html_path = '/tmp/jike_qr_login.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"[*] QR code saved to: {html_path}", file=sys.stderr)
        print(f"[*] Open in browser: file://{html_path}", file=sys.stderr)

        # Also print ASCII for terminal users
        qr_ascii = qrcode.QRCode(version=1, box_size=2, border=2)
        qr_ascii.add_data(data)
        qr_ascii.make(fit=True)
        qr_ascii.print_ascii(out=sys.stderr)

        return True
    except ImportError:
        return False


def poll_confirmation(uuid: str, timeout: int = 180) -> Optional[dict]:
    for _ in range(timeout):
        try:
            resp = requests.get(
                f"{API_BASE}/sessions.wait_for_confirmation?uuid={uuid}",
                headers=HEADERS,
            )
        except requests.RequestException:
            time.sleep(1)
            continue

        if resp.status_code == 200:
            body = resp.json()
            access = body.get("x-jike-access-token") or body.get("access_token")
            refresh = body.get("x-jike-refresh-token") or body.get("refresh_token")
            if access and refresh:
                return {"access_token": access, "refresh_token": refresh}
            return None

        if resp.status_code == 400:
            time.sleep(1)
            continue

        time.sleep(1)
    return None


def refresh_tokens(refresh_token: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/app_auth_tokens.refresh",
        headers={**HEADERS, "Content-Type": "application/json", "x-jike-refresh-token": refresh_token},
        json={},
    )
    resp.raise_for_status()
    return {
        "access_token": resp.headers.get("x-jike-access-token", ""),
        "refresh_token": resp.headers.get("x-jike-refresh-token", refresh_token),
    }


if __name__ == "__main__":
    uuid = create_session()
    print(f"[+] Session: {uuid}", file=sys.stderr)

    qr_payload = build_qr_payload(uuid)
    if not render_qr(qr_payload, uuid):
        print("[*] Install 'qrcode' for terminal QR, or scan:", file=sys.stderr)
        print(f"    {qr_payload}", file=sys.stderr)

    print("[*] Waiting for scan...", file=sys.stderr)
    tokens = poll_confirmation(uuid)

    if not tokens:
        print("[!] Timeout", file=sys.stderr)
        sys.exit(1)

    print("[+] Scan confirmed, refreshing...", file=sys.stderr)
    tokens = refresh_tokens(tokens["refresh_token"])
    print("[+] Ready", file=sys.stderr)

    json.dump(tokens, sys.stdout, indent=2)
    print()
