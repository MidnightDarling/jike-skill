"""
Jike QR Authentication
Scan-to-login flow — no passwords needed.

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

from .types import API_BASE, DEFAULT_HEADERS, REQUEST_TIMEOUT_SEC, TokenPair

POLL_INTERVAL_SEC = 1
POLL_TIMEOUT_SEC = 180
POLL_REQUEST_TIMEOUT_SEC = 60  # long-poll: server holds connection while waiting for QR scan

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
    """Convert a QRCode object to a base64-encoded PNG string."""
    buf = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _write_qr_html(png_b64: str, caption: str = "") -> Path:
    """Write the QR HTML page to a unique tempfile and return its path.

    Uses ``tempfile.NamedTemporaryFile`` so the path is unpredictable (no
    symlink/TOCTOU window) and the file is created with mode ``0o600`` on
    POSIX. The caller is expected to ``unlink`` the path once the auth flow
    no longer needs it.
    """
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
    """Render the QR through both an HTML file and a terminal ASCII view.

    Both channels are gated by the optional ``qrcode`` library. Either
    channel may individually fail (filesystem error, encoding error) without
    preventing the other; the returned ``QRRender`` describes what worked.
    Returns ``QRRender(html_path=None, ascii_printed=False)`` if ``qrcode``
    is not installed.
    """
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


def _cleanup_qr_html(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def authenticate() -> TokenPair:
    """Full QR login flow. Returns TokenPair or exits on failure."""
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
