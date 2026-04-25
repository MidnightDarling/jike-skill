#!/usr/bin/env python3
"""
Jike QR Authentication (standalone)
Run directly: python3 scripts/auth.py
No pip install required — only needs `requests` (and optional `qrcode[pil]`).

Author: Claude Opus 4.5 (v0.1) · Claude Opus 4.7 (v0.4 secure QR HTML)
"""

import base64
import html
import json
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
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

QR_VERSION = 1
QR_BOX_SIZE = 10
QR_BORDER = 2

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Jike Login QR</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          display: flex; flex-direction: column; align-items: center;
          padding: 32px; background: #fafafa; color: #222; }}
  img  {{ width: 320px; height: 320px; image-rendering: pixelated;
          border: 1px solid #eee; }}
  p    {{ margin: 12px 0; font-size: 14px; color: #666; }}
  code {{ background: #eee; padding: 2px 6px; border-radius: 3px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
</style>
</head>
<body>
  <h2>Scan with Jike app</h2>
  <img alt="Jike login QR" src="data:image/png;base64,{png_b64}">
  <p>Session: <code>{caption}</code></p>
  <p>This page is only valid until the auth flow completes.</p>
</body>
</html>
"""


@dataclass(frozen=True)
class QRRender:
    """Outcome of rendering a QR code through both available channels."""

    html_path: Optional[Path]
    ascii_printed: bool

    @property
    def any_visible(self) -> bool:
        return self.html_path is not None or self.ascii_printed


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


def _build_qr(data: str):
    """Build a QRCode object reusable for both image and ASCII output.

    Caller is responsible for handling ImportError if `qrcode` is not installed.
    """
    import qrcode  # local import: optional dependency

    qr = qrcode.QRCode(version=QR_VERSION, box_size=QR_BOX_SIZE, border=QR_BORDER)
    qr.add_data(data)
    qr.make(fit=True)
    return qr


def _qr_to_png_base64(qr) -> str:
    buf = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _write_qr_html(png_b64: str, caption: str = "") -> Path:
    """Write the QR HTML page to a unique tempfile (mode 0o600 on POSIX)."""
    f = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="jike_qr_",
        suffix=".html",
        delete=False,
    )
    path = Path(f.name)
    try:
        with f:
            f.write(
                _HTML_TEMPLATE.format(
                    png_b64=png_b64,
                    caption=html.escape(caption),
                )
            )
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path


def render_qr(data: str, caption: str = "") -> QRRender:
    """Render the QR through both an HTML file and a terminal ASCII view."""
    try:
        qr = _build_qr(data)
    except ImportError:
        return QRRender(html_path=None, ascii_printed=False)

    html_path: Optional[Path] = None
    try:
        png_b64 = _qr_to_png_base64(qr)
        html_path = _write_qr_html(png_b64, caption=caption)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[!] QR HTML generation skipped: {exc}", file=sys.stderr)
        html_path = None

    ascii_printed = False
    try:
        qr.print_ascii(out=sys.stderr)
        ascii_printed = True
    except (OSError, UnicodeEncodeError) as exc:
        print(f"[!] QR ASCII rendering skipped: {exc}", file=sys.stderr)

    return QRRender(html_path=html_path, ascii_printed=ascii_printed)


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


def _cleanup_qr_html(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


if __name__ == "__main__":
    uuid = create_session()
    print(f"[+] Session: {uuid}", file=sys.stderr)

    qr_payload = build_qr_payload(uuid)
    rendered = render_qr(qr_payload, caption=uuid)

    if rendered.html_path is not None:
        print(
            f"[+] QR HTML (open in browser): {rendered.html_path.as_uri()}",
            file=sys.stderr,
        )
    if not rendered.any_visible:
        print("[*] Install 'qrcode' for terminal/HTML QR, or scan manually:", file=sys.stderr)
        print(f"    {qr_payload}", file=sys.stderr)

    print("[*] Waiting for scan...", file=sys.stderr)

    try:
        tokens = poll_confirmation(uuid)
    finally:
        _cleanup_qr_html(rendered.html_path)

    if not tokens:
        print("[!] Timeout", file=sys.stderr)
        sys.exit(1)

    print("[+] Scan confirmed, refreshing...", file=sys.stderr)
    tokens = refresh_tokens(tokens["refresh_token"], tokens["access_token"])
    print("[+] Ready", file=sys.stderr)

    json.dump(tokens, sys.stdout, indent=2)
    print()
