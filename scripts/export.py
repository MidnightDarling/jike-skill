#!/usr/bin/env python3
"""
Export all posts from a Jike user account to Markdown.

Usage:
  python3 scripts/export.py --username USERNAME \
    --access-token TOKEN --refresh-token TOKEN \
    [--output FILE] [--download-images] [--images-dir DIR]

Features:
  - Paginates through ALL posts automatically
  - Includes images (inline links or downloaded)
  - Includes repost/share content
  - Chronological order (oldest first)
  - Progress output to stderr

Author: Claude Opus 4.6
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

API_BASE = "https://api.ruguoapp.com"
REQUEST_TIMEOUT_SEC = 15
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

PAGE_SIZE = 20
RATE_LIMIT_DELAY = 0.5  # seconds between API calls


def _make_headers(access_token: str) -> dict:
    return {
        **HEADERS,
        "Content-Type": "application/json",
        "x-jike-access-token": access_token,
    }


def _refresh_tokens(refresh_token: str, access_token: str = "") -> tuple[str, str]:
    resp = requests.post(
        f"{API_BASE}/app_auth_tokens.refresh",
        headers={
            **HEADERS,
            "Content-Type": "application/json",
            "x-jike-refresh-token": refresh_token,
        },
        json={},
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return (
        resp.headers.get("x-jike-access-token", access_token),
        resp.headers.get("x-jike-refresh-token", refresh_token),
    )


def _api_call(
    method: str,
    path: str,
    access_token: str,
    refresh_token: str,
    retry: bool = True,
    **kwargs,
) -> tuple[dict, str, str]:
    """Make API call with auto-refresh. Returns (data, current_at, current_rt)."""
    hdrs = _make_headers(access_token)
    resp = requests.request(
        method,
        f"{API_BASE}{path}",
        headers=hdrs,
        timeout=REQUEST_TIMEOUT_SEC,
        **kwargs,
    )

    if resp.status_code == 401 and retry:
        access_token, refresh_token = _refresh_tokens(refresh_token, access_token)
        return _api_call(
            method, path, access_token, refresh_token, retry=False, **kwargs
        )

    resp.raise_for_status()
    data = resp.json() if resp.content else {}
    return data, access_token, refresh_token


def fetch_user_profile(
    username: str, at: str, rt: str
) -> tuple[dict, str, str]:
    return _api_call("GET", f"/1.0/users/profile?username={username}", at, rt)


def fetch_user_posts(
    username: str,
    at: str,
    rt: str,
    load_more_key: Optional[dict] = None,
) -> tuple[dict, str, str]:
    body: dict = {"username": username}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _api_call("POST", "/1.0/userPost/listMore", at, rt, json=body)


def fetch_all_posts(
    username: str, at: str, rt: str
) -> tuple[list[dict], str, str]:
    """Paginate through all posts for a user. Returns (posts, at, rt)."""
    all_posts = []
    load_more_key = None
    page = 0

    while True:
        page += 1
        print(f"  Fetching page {page}...", file=sys.stderr, end="", flush=True)

        data, at, rt = fetch_user_posts(
            username, at, rt, load_more_key=load_more_key
        )

        posts = data.get("data", [])
        all_posts.extend(posts)
        print(f" got {len(posts)} posts (total: {len(all_posts)})", file=sys.stderr)

        load_more_key = data.get("loadMoreKey")
        if not load_more_key or not posts:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return all_posts, at, rt


def download_image(url: str, images_dir: Path, post_index: int, img_index: int) -> str:
    """Download image and return local relative path."""
    ext = Path(urlparse(url).path).suffix or ".jpg"
    filename = f"post_{post_index:04d}_img_{img_index}{ext}"
    filepath = images_dir / filename

    if filepath.exists():
        return str(filepath.relative_to(images_dir.parent))

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        filepath.write_bytes(resp.content)
        return str(filepath.relative_to(images_dir.parent))
    except requests.RequestException as e:
        print(f"  Warning: failed to download {url}: {e}", file=sys.stderr)
        return url


def _extract_pictures(post: dict) -> list[str]:
    """Extract image URLs from a post."""
    pictures = post.get("pictures", []) or []
    urls = []
    for pic in pictures:
        url = (
            pic.get("picUrl")
            or pic.get("middlePicUrl")
            or pic.get("thumbnailUrl")
            or ""
        )
        if url:
            urls.append(url)
    return urls


def _extract_link(post: dict) -> Optional[dict]:
    """Extract link info if present."""
    link = post.get("linkInfo")
    if not link:
        return None
    return {
        "title": link.get("title", ""),
        "url": link.get("linkUrl", ""),
    }


def _extract_repost_target(post: dict) -> Optional[dict]:
    """Extract repost target info."""
    target = post.get("target")
    if not target:
        return None
    user = target.get("user", {})
    return {
        "content": target.get("content", ""),
        "author": user.get("screenName", user.get("username", "unknown")),
        "pictures": _extract_pictures(target),
        "link": _extract_link(target),
        "id": target.get("id", ""),
        "type": target.get("type", ""),
    }


def _extract_topic(post: dict) -> Optional[str]:
    """Extract topic name if present."""
    topic = post.get("topic")
    if not topic:
        return None
    return topic.get("content", "")


def _format_timestamp(iso_str: str) -> str:
    """Format ISO timestamp to readable string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return iso_str


def post_to_markdown(
    post: dict,
    index: int,
    download_images: bool = False,
    images_dir: Optional[Path] = None,
) -> str:
    """Convert a single post to markdown."""
    lines = []

    post_type = post.get("type", "ORIGINAL_POST")
    created_at = post.get("createdAt", "")
    content = post.get("content", "")
    post_id = post.get("id", "")
    topic = _extract_topic(post)
    pictures = _extract_pictures(post)
    link = _extract_link(post)
    repost = _extract_repost_target(post)

    timestamp = _format_timestamp(created_at)
    lines.append(f"### {index}. {timestamp}")
    lines.append("")

    if topic:
        lines.append(f"> Topic: **{topic}**")
        lines.append("")

    if post_type == "REPOST" and repost:
        lines.append(f"*Repost from @{repost['author']}*")
        lines.append("")

    if content:
        lines.append(content)
        lines.append("")

    if pictures:
        for i, url in enumerate(pictures):
            if download_images and images_dir:
                img_path = download_image(url, images_dir, index, i)
                lines.append(f"![img]({img_path})")
            else:
                lines.append(f"![img]({url})")
        lines.append("")

    if link:
        title = link["title"] or link["url"]
        lines.append(f"[{title}]({link['url']})")
        lines.append("")

    if repost:
        lines.append("> **@{}**:".format(repost["author"]))
        if repost["content"]:
            for line in repost["content"].split("\n"):
                lines.append(f"> {line}")
        if repost["pictures"]:
            lines.append(">")
            for i, url in enumerate(repost["pictures"]):
                if download_images and images_dir:
                    img_path = download_image(
                        url, images_dir, index, 100 + i
                    )
                    lines.append(f"> ![img]({img_path})")
                else:
                    lines.append(f"> ![img]({url})")
        if repost.get("link"):
            rlink = repost["link"]
            rtitle = rlink["title"] or rlink["url"]
            lines.append(f"> [{rtitle}]({rlink['url']})")
        lines.append("")

    lines.append(f"<sub>ID: {post_id}</sub>")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def export_to_markdown(
    posts: list[dict],
    user_info: dict,
    output_path: str,
    download_images: bool = False,
    images_dir: Optional[Path] = None,
) -> None:
    """Export posts to a markdown file."""
    screen_name = user_info.get("screenName", "")
    username = user_info.get("username", "")
    bio = user_info.get("bio", "")

    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("createdAt", ""),
    )

    lines = []
    lines.append(f"# {screen_name} (@{username}) - Jike Posts Export")
    lines.append("")
    lines.append(f"**Bio**: {bio}")
    lines.append(f"**Total posts**: {len(sorted_posts)}")
    lines.append(f"**Exported at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, post in enumerate(sorted_posts, 1):
        md = post_to_markdown(post, i, download_images, images_dir)
        lines.append(md)

    content = "\n".join(lines)

    if output_path == "-":
        sys.stdout.write(content)
    else:
        Path(output_path).write_text(content, encoding="utf-8")
        print(f"Exported {len(sorted_posts)} posts to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Export all Jike posts from a user to Markdown"
    )
    parser.add_argument("--username", required=True, help="Jike username to export")
    access_env = os.getenv("JIKE_ACCESS_TOKEN") or None  # coerce "" -> None
    refresh_env = os.getenv("JIKE_REFRESH_TOKEN") or None  # coerce "" -> None
    parser.add_argument(
        "--access-token",
        default=access_env,
        required=access_env is None,
        help="Access token (or set JIKE_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--refresh-token",
        default=refresh_env,
        required=refresh_env is None,
        help="Refresh token (or set JIKE_REFRESH_TOKEN)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output markdown file (default: <username>_jike_export.md)"
    )
    parser.add_argument(
        "--download-images", action="store_true",
        help="Download images locally instead of using URLs"
    )
    parser.add_argument(
        "--images-dir", default=None,
        help="Directory for downloaded images (default: <username>_images)"
    )
    parser.add_argument(
        "--json-dump", action="store_true",
        help="Also save raw JSON data alongside the markdown"
    )

    args = parser.parse_args()
    at, rt = args.access_token, args.refresh_token

    output_path = args.output or f"{args.username}_jike_export.md"
    images_dir = None

    if args.download_images:
        images_dir = Path(args.images_dir or f"{args.username}_images")
        images_dir.mkdir(parents=True, exist_ok=True)
        print(f"Images will be saved to: {images_dir}", file=sys.stderr)

    try:
        print(f"Fetching profile for @{args.username}...", file=sys.stderr)
        profile_data, at, rt = fetch_user_profile(args.username, at, rt)
        user_info = profile_data.get("user", profile_data)
        screen_name = user_info.get("screenName", args.username)
        print(f"  Found: {screen_name}", file=sys.stderr)

        print(f"Fetching all posts for @{args.username}...", file=sys.stderr)
        all_posts, at, rt = fetch_all_posts(args.username, at, rt)

        if not all_posts:
            print("No posts found.", file=sys.stderr)
            sys.exit(0)

        if args.json_dump:
            json_path = output_path.replace(".md", ".json")
            Path(json_path).write_text(
                json.dumps(all_posts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Raw JSON saved to: {json_path}", file=sys.stderr)

        export_to_markdown(all_posts, user_info, output_path, args.download_images, images_dir)

    except requests.RequestException as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExport interrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
