import argparse
import base64
import html
import json
import os
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

POLL_INTERVAL_SEC, POLL_TIMEOUT_SEC, POLL_REQUEST_TIMEOUT_SEC, SERVER_ERROR_LIMIT = 1, 180, 60, 3
QR_VERSION, QR_BOX_SIZE, QR_BORDER = 1, 10, 2
_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Jike Login QR</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;flex-direction:column;align-items:center;padding:32px;background:#fafafa;color:#222}}img{{width:320px;height:320px;image-rendering:pixelated;border:1px solid #eee}}p{{margin:12px 0;font-size:14px;color:#666}}code{{background:#eee;padding:2px 6px;border-radius:3px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}</style>
</head><body><h2>Scan with Jike app</h2>
<img alt="Jike login QR" src="data:image/png;base64,{png_b64}">
<p>Session: <code>{caption}</code></p>
<p>This page is only valid until the auth flow completes.</p></body></html>
"""
@dataclass(frozen=True)
class QRRender:
    html_path: Optional[Path]
    ascii_printed: bool

    @property
    def any_visible(self) -> bool:
        return self.html_path is not None or self.ascii_printed
def _post(path: str, headers: Optional[dict] = None, **kwargs) -> requests.Response:
    merged = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    return requests.post(f"{API_BASE}{path}", headers=merged, timeout=REQUEST_TIMEOUT_SEC, **kwargs)
def _get(path: str, timeout: float = REQUEST_TIMEOUT_SEC) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers=DEFAULT_HEADERS, timeout=timeout)
def create_session() -> str:
    resp = _post("/sessions.create")
    resp.raise_for_status()
    return resp.json()["uuid"]

def build_qr_payload(uuid: str) -> str:
    scan_url = f"https://www.okjike.com/account/scan?uuid={uuid}"
    return "jike://page.jk/web?url=" + urllib.parse.quote(scan_url, safe="") + "&displayHeader=false&displayFooter=false"

def _build_qr(data: str):
    import qrcode
    qr = qrcode.QRCode(version=QR_VERSION, box_size=QR_BOX_SIZE, border=QR_BORDER)
    qr.add_data(data)
    qr.make(fit=True)
    return qr

def _qr_to_png_base64(qr) -> str:
    buf = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    png = buf.getvalue()
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("QR image renderer did not produce PNG bytes")
    return base64.b64encode(png).decode("ascii")

def _write_qr_html(png_b64: str, caption: str = "") -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="jike_qr_", suffix=".html", delete=False)
    path = Path(f.name)
    try:
        with f:
            f.write(_HTML_TEMPLATE.format(png_b64=png_b64, caption=html.escape(caption)))
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path

def render_qr(data: str, caption: str = "") -> QRRender:
    try:
        qr = _build_qr(data)
    except ImportError:
        return QRRender(html_path=None, ascii_printed=False)
    html_path: Optional[Path] = None
    try:
        html_path = _write_qr_html(_qr_to_png_base64(qr), caption=caption)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[!] QR HTML generation skipped: {exc}", file=sys.stderr)
    ascii_printed = False
    try:
        qr.print_ascii(out=sys.stderr)
        ascii_printed = True
    except (OSError, UnicodeEncodeError) as exc:
        print(f"[!] QR ASCII rendering skipped: {exc}", file=sys.stderr)
    return QRRender(html_path=html_path, ascii_printed=ascii_printed)

def _extract_tokens(resp: requests.Response) -> Optional[TokenPair]:
    body = {}
    try:
        data = resp.json()
        body = data if isinstance(data, dict) else {}
    except (ValueError, AttributeError):
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
    return TokenPair(access_token=access, refresh_token=refresh) if access and refresh else None

def poll_confirmation(uuid: str) -> Optional[TokenPair]:
    attempts = max(1, POLL_TIMEOUT_SEC // POLL_INTERVAL_SEC)
    deadline, server_errors = time.monotonic() + POLL_TIMEOUT_SEC, 0
    path = "/sessions.wait_for_confirmation?uuid=" + urllib.parse.quote(uuid, safe="")
    for _ in range(attempts):
        if time.monotonic() >= deadline:
            break
        remaining = max(0.1, deadline - time.monotonic())
        try:
            resp = _get(path, timeout=min(POLL_REQUEST_TIMEOUT_SEC, remaining))
        except requests.RequestException:
            resp = None
        if resp is not None:
            server_errors = server_errors + 1 if resp.status_code >= 500 else 0
            if server_errors >= SERVER_ERROR_LIMIT:
                return None
            if resp.status_code == 200:
                return _extract_tokens(resp)
        sleep_for = min(POLL_INTERVAL_SEC, max(0, deadline - time.monotonic()))
        if sleep_for:
            time.sleep(sleep_for)
    return None

def refresh_tokens(token_pair: TokenPair) -> TokenPair:
    resp = _post("/app_auth_tokens.refresh", headers={"x-jike-refresh-token": token_pair.refresh_token}, json={})
    resp.raise_for_status()
    return TokenPair(
        access_token=resp.headers.get("x-jike-access-token", token_pair.access_token),
        refresh_token=resp.headers.get("x-jike-refresh-token", token_pair.refresh_token),
    )

def _cleanup_qr_html(path: Optional[Path]) -> None:
    try:
        if path is not None:
            path.unlink(missing_ok=True)
    except OSError:
        pass

def authenticate() -> TokenPair:
    try:
        uuid = create_session()
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"[!] Could not create auth session: {exc.__class__.__name__}", file=sys.stderr)
        sys.exit(1)
    print(f"[+] Session: {uuid}", file=sys.stderr)
    qr_payload = build_qr_payload(uuid)
    rendered = render_qr(qr_payload, caption=uuid)
    if rendered.html_path is not None:
        print(f"[+] QR HTML (open in browser): {rendered.html_path.as_uri()}", file=sys.stderr)
    if not rendered.any_visible:
        print("[*] Install 'qrcode' for QR rendering, or scan manually:", file=sys.stderr)
        print(f"    {qr_payload}", file=sys.stderr)
    print("[*] Waiting for scan...", file=sys.stderr)
    try:
        tokens = poll_confirmation(uuid)
    finally:
        _cleanup_qr_html(rendered.html_path)
    if not tokens:
        print("[!] Timeout or invalid confirmation response", file=sys.stderr)
        sys.exit(1)
    print("[+] Scan confirmed, refreshing tokens...", file=sys.stderr)
    try:
        tokens = refresh_tokens(tokens)
    except requests.RequestException as exc:
        print(f"[!] Token refresh failed: {exc.__class__.__name__}", file=sys.stderr)
        sys.exit(1)
    print("[+] Ready", file=sys.stderr)
    return tokens

def _write_token_file(path: Path, tokens: TokenPair) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(tokens.to_dict(), f, indent=2)
        f.write("\n")

def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Authenticate with Jike by QR scan")
    parser.add_argument("--out", help="Write token JSON to a 0600 file")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    tokens = authenticate()
    if args.out:
        _write_token_file(Path(args.out), tokens)
        print(f"[+] Tokens written to {args.out} with mode 0600", file=sys.stderr)
        return
    json.dump(tokens.to_dict(), sys.stdout, indent=2)
    print()
