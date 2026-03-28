"""
Jike QR Authentication
Scan-to-login flow — no passwords needed.

Author: Claude Opus 4.5
"""

import json
import sys
import time
import urllib.parse
from typing import Optional

import requests

from .types import API_BASE, DEFAULT_HEADERS, REQUEST_TIMEOUT_SEC, TokenPair

POLL_INTERVAL_SEC = 1
POLL_TIMEOUT_SEC = 180
POLL_REQUEST_TIMEOUT_SEC = 60  # long-poll: server holds connection while waiting for QR scan


def _post(path: str, headers: Optional[dict] = None, **kwargs) -> requests.Response:
    merged = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    return requests.post(
        f"{API_BASE}{path}",
        headers=merged,
        timeout=REQUEST_TIMEOUT_SEC,
        **kwargs,
    )


def _get(path: str, timeout: int = REQUEST_TIMEOUT_SEC) -> requests.Response:
    return requests.get(
        f"{API_BASE}{path}",
        headers={**DEFAULT_HEADERS},
        timeout=timeout,
    )


def create_session() -> str:
    """Create a login session, return uuid."""
    resp = _post("/sessions.create")
    resp.raise_for_status()
    return resp.json()["uuid"]


def build_qr_payload(uuid: str) -> str:
    """Build the jike:// deep-link QR payload."""
    scan_url = f"https://www.okjike.com/account/scan?uuid={uuid}"
    return (
        "jike://page.jk/web?url="
        + urllib.parse.quote(scan_url, safe="")
        + "&displayHeader=false&displayFooter=false"
    )


def render_qr(data: str) -> bool:
    """Render QR code in terminal. Returns False if qrcode lib unavailable."""
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        qr.print_ascii(out=sys.stderr)
        return True
    except ImportError:
        return False


def _extract_tokens(resp: requests.Response) -> Optional[TokenPair]:
    """Extract tokens from confirmation response (body or headers)."""
    body: dict = {}
    try:
        body = resp.json()
    except (ValueError, KeyError):
        pass

    access = (
        body.get("x-jike-access-token")
        or body.get("access_token")
        or resp.headers.get("x-jike-access-token")
    )
    refresh = (
        body.get("x-jike-refresh-token")
        or body.get("refresh_token")
        or resp.headers.get("x-jike-refresh-token")
    )

    if access and refresh:
        return TokenPair(access_token=access, refresh_token=refresh)
    return None


def poll_confirmation(uuid: str) -> Optional[TokenPair]:
    """Poll until user scans QR. Returns TokenPair or None on timeout."""
    attempts = POLL_TIMEOUT_SEC // POLL_INTERVAL_SEC

    for _ in range(attempts):
        try:
            resp = _get(
                f"/sessions.wait_for_confirmation?uuid={uuid}",
                timeout=POLL_REQUEST_TIMEOUT_SEC,
            )
        except requests.RequestException:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        if resp.status_code == 200:
            return _extract_tokens(resp)

        if resp.status_code == 400:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        time.sleep(POLL_INTERVAL_SEC)

    return None


def refresh_tokens(token_pair: TokenPair) -> TokenPair:
    """Normalize tokens via refresh endpoint."""
    resp = _post(
        "/app_auth_tokens.refresh",
        headers={"x-jike-refresh-token": token_pair.refresh_token},
        json={},
    )
    resp.raise_for_status()

    return TokenPair(
        access_token=resp.headers.get(
            "x-jike-access-token", token_pair.access_token
        ),
        refresh_token=resp.headers.get(
            "x-jike-refresh-token", token_pair.refresh_token
        ),
    )


def authenticate() -> TokenPair:
    """Full QR login flow. Returns TokenPair or exits on failure."""
    uuid = create_session()
    print(f"[+] Session: {uuid}", file=sys.stderr)

    qr_payload = build_qr_payload(uuid)
    if not render_qr(qr_payload):
        print("[*] Install 'qrcode' for terminal QR:", file=sys.stderr)
        print(f"    {qr_payload}", file=sys.stderr)

    print("[*] Waiting for scan...", file=sys.stderr)

    tokens = poll_confirmation(uuid)
    if not tokens:
        print("[!] Timeout — no scan detected", file=sys.stderr)
        sys.exit(1)

    print("[+] Scan confirmed, refreshing tokens...", file=sys.stderr)
    tokens = refresh_tokens(tokens)
    print("[+] Ready", file=sys.stderr)

    return tokens


def main() -> None:
    """CLI entry point: authenticate and print tokens as JSON."""
    tokens = authenticate()
    json.dump(tokens.to_dict(), sys.stdout, indent=2)
    print()
