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
REQUEST_TIMEOUT_SEC = 15
POLL_REQUEST_TIMEOUT_SEC = 60  # long-poll: server holds connection while waiting for QR scan
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
        timeout=REQUEST_TIMEOUT_SEC,
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


def render_qr(data: str) -> bool:
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        qr.print_ascii(out=sys.stderr)
        return True
    except ImportError:
        return False


def poll_confirmation(uuid: str, timeout: int = 180) -> Optional[dict]:
    for _ in range(timeout):
        try:
            resp = requests.get(
                f"{API_BASE}/sessions.wait_for_confirmation?uuid={uuid}",
                headers=HEADERS,
                timeout=POLL_REQUEST_TIMEOUT_SEC,
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


def refresh_tokens(refresh_token: str, access_token: str = "") -> dict:
    resp = requests.post(
        f"{API_BASE}/app_auth_tokens.refresh",
        headers={**HEADERS, "Content-Type": "application/json", "x-jike-refresh-token": refresh_token},
        json={},
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return {
        "access_token": resp.headers.get("x-jike-access-token", access_token),
        "refresh_token": resp.headers.get("x-jike-refresh-token", refresh_token),
    }


if __name__ == "__main__":
    uuid = create_session()
    print(f"[+] Session: {uuid}", file=sys.stderr)

    qr_payload = build_qr_payload(uuid)
    if not render_qr(qr_payload):
        print("[*] Install 'qrcode' for terminal QR, or scan:", file=sys.stderr)
        print(f"    {qr_payload}", file=sys.stderr)

    print("[*] Waiting for scan...", file=sys.stderr)
    tokens = poll_confirmation(uuid)

    if not tokens:
        print("[!] Timeout", file=sys.stderr)
        sys.exit(1)

    print("[+] Scan confirmed, refreshing...", file=sys.stderr)
    tokens = refresh_tokens(tokens["refresh_token"], tokens["access_token"])
    print("[+] Ready", file=sys.stderr)

    json.dump(tokens, sys.stdout, indent=2)
    print()
