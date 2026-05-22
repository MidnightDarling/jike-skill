"""CLI and API calls for exporting Jike posts."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import requests

from .export_utils import atomic_write, export_to_markdown, json_path_for, validate_username
from .types import API_BASE, DEFAULT_HEADERS, JikeResponse, REQUEST_TIMEOUT_SEC

RATE_LIMIT_DELAY = 0.5

def _headers(access_token: str) -> dict:
    return {**DEFAULT_HEADERS, "Content-Type": "application/json", "x-jike-access-token": access_token}

def _refresh(refresh_token: str, access_token: Optional[str] = None) -> tuple[str, str]:
    resp = requests.post(
        f"{API_BASE}/app_auth_tokens.refresh",
        headers={**DEFAULT_HEADERS, "Content-Type": "application/json", "x-jike-refresh-token": refresh_token},
        json={},
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return (
        resp.headers.get("x-jike-access-token", access_token or ""),
        resp.headers.get("x-jike-refresh-token", refresh_token),
    )

def _retry_after(resp: requests.Response) -> float:
    try:
        return min(max(float(resp.headers.get("Retry-After", "1")), 0), 30)
    except ValueError:
        return 1.0

def _api_call(
    method: str, path: str, at: str, rt: str, retry: bool = True, retry_429: bool = True, **kwargs
) -> tuple[JikeResponse, str, str]:
    resp = requests.request(method, f"{API_BASE}{path}", headers=_headers(at), timeout=REQUEST_TIMEOUT_SEC, **kwargs)
    if resp.status_code == 401 and retry:
        at, rt = _refresh(rt, at)
        return _api_call(method, path, at, rt, retry=False, **kwargs)
    if resp.status_code == 429 and retry_429:
        time.sleep(_retry_after(resp))
        return _api_call(method, path, at, rt, retry_429=False, **kwargs)
    resp.raise_for_status()
    return (resp.json() if resp.content else {}), at, rt

def fetch_user_profile(username: str, at: str, rt: str) -> tuple[JikeResponse, str, str]:
    return _api_call("GET", f"/1.0/users/profile?username={quote(username, safe='')}", at, rt)

def fetch_user_posts(username: str, at: str, rt: str, load_more_key: Optional[dict] = None) -> tuple[JikeResponse, str, str]:
    body: dict = {"username": username}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _api_call("POST", "/1.0/userPost/listMore", at, rt, json=body)

def _load_checkpoint(path: Path, username: str) -> tuple[list[dict], Optional[dict]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid checkpoint file") from exc
    if data.get("username") != username or not isinstance(data.get("posts"), list):
        raise ValueError("checkpoint does not match username")
    return data["posts"], data.get("loadMoreKey")

def _save_checkpoint(path: Path, username: str, posts: list[dict], load_more_key: Optional[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"username": username, "posts": posts, "loadMoreKey": load_more_key}
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

def fetch_all_posts(
    username: str,
    at: str,
    rt: str,
    checkpoint_path: Optional[Path] = None,
    resume: bool = False,
) -> tuple[list[dict], str, str]:
    posts, load_more_key = _load_checkpoint(checkpoint_path, username) if resume and checkpoint_path else ([], None)
    if resume and posts and load_more_key is None:
        return posts, at, rt
    page = 0
    while True:
        page += 1
        print(f"  Fetching page {page}...", file=sys.stderr, end="", flush=True)
        data, at, rt = fetch_user_posts(username, at, rt, load_more_key=load_more_key)
        batch = data.get("data", [])
        posts.extend(batch)
        print(f" got {len(batch)} posts (total: {len(posts)})", file=sys.stderr)
        load_more_key = data.get("loadMoreKey")
        if checkpoint_path:
            _save_checkpoint(checkpoint_path, username, posts, load_more_key)
        if not load_more_key or not batch:
            return posts, at, rt
        time.sleep(RATE_LIMIT_DELAY)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Jike posts to Markdown")
    access_env = os.getenv("JIKE_ACCESS_TOKEN") or None
    refresh_env = os.getenv("JIKE_REFRESH_TOKEN") or None
    parser.add_argument("--username", required=True)
    parser.add_argument("--access-token", default=access_env, required=access_env is None)
    parser.add_argument("--refresh-token", default=refresh_env, required=refresh_env is None)
    parser.add_argument("--output", "-o")
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--images-dir")
    parser.add_argument("--json-dump", action="store_true")
    parser.add_argument("--checkpoint", help="Write resumable pagination checkpoint JSON")
    parser.add_argument("--resume", action="store_true", help="Resume from --checkpoint")
    return parser

def _warn_process_visible_tokens(argv: list[str]) -> None:
    if "--access-token" in argv or "--refresh-token" in argv:
        print("[!] Token flags may be visible to other local users; prefer env vars.", file=sys.stderr)

def main(argv: Optional[list[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    _warn_process_visible_tokens(argv)
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        stem = validate_username(args.username)
    except ValueError as exc:
        parser.error(str(exc))
    if args.resume and not args.checkpoint:
        parser.error("--resume requires --checkpoint")
    output_path = args.output or f"{stem}_jike_export.md"
    images_dir = Path(args.images_dir or f"{stem}_images") if args.download_images else None
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else None
    at, rt = args.access_token, args.refresh_token
    try:
        print(f"Fetching profile for @{args.username}...", file=sys.stderr)
        profile_data, at, rt = fetch_user_profile(args.username, at, rt)
        user_info = profile_data.get("user", profile_data)
        print(f"Fetching all posts for @{args.username}...", file=sys.stderr)
        posts, _, _ = fetch_all_posts(args.username, at, rt, checkpoint_path, args.resume)
        if args.json_dump:
            path = json_path_for(output_path, args.username)
            atomic_write(path, json.dumps(posts, ensure_ascii=False, indent=2) + "\n")
            print(f"Raw JSON saved to: {path}", file=sys.stderr)
        export_to_markdown(posts, user_info, output_path, args.download_images, images_dir)
    except requests.RequestException as exc:
        print(json.dumps({"error": exc.__class__.__name__}), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(json.dumps({"error": exc.__class__.__name__}), file=sys.stderr)
        sys.exit(1)
