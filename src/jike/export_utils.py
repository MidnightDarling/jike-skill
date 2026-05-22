"""Markdown and image helpers for Jike exports."""
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import requests

from .types import IMAGE_HOST_SUFFIXES, host_matches

MAX_IMAGE_BYTES = 20 * 1024 * 1024
SAFE_USERNAME = re.compile(r"^[A-Za-z0-9_-]+$")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

def validate_username(username: str) -> str:
    if not SAFE_USERNAME.fullmatch(username):
        raise ValueError("username must contain only letters, numbers, '_' or '-'")
    return username

def json_path_for(output_path: str, username: str) -> Path:
    if output_path == "-":
        return Path(f"{validate_username(username)}_jike_export.json")
    return Path(output_path).with_suffix(".json")

def clean(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(ch if ch in "\n\t" or ord(ch) >= 32 else " " for ch in text)

def md_text(value: object) -> str:
    return html.escape(clean(value), quote=False).replace("|", "\\|")

def md_label(value: object) -> str:
    text = html.escape(clean(value).replace("\n", " "), quote=False)
    for char in "\\[]()":
        text = text.replace(char, "\\" + char)
    return text

def safe_url(url: object) -> Optional[str]:
    text = clean(url).strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text

def md_url(url: str) -> str:
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")

def _image_host_suffixes() -> tuple[str, ...]:
    configured = os.getenv("JIKE_EXPORT_IMAGE_HOSTS", "")
    extra = tuple(host.strip().lower().strip(".") for host in configured.split(",") if host.strip())
    return IMAGE_HOST_SUFFIXES + extra

def extract_pictures(post: dict) -> list[str]:
    urls = []
    for pic in post.get("pictures", []) or []:
        url = safe_url(pic.get("picUrl") or pic.get("middlePicUrl") or pic.get("thumbnailUrl") or "")
        if url:
            urls.append(url)
    return urls

def extract_link(post: dict) -> Optional[dict]:
    link = post.get("linkInfo")
    if not link:
        return None
    url = safe_url(link.get("linkUrl", ""))
    return {"title": link.get("title", "") or url, "url": url} if url else None

def _relative(path: Path, output_dir: Path) -> str:
    try:
        return str(path.relative_to(output_dir))
    except ValueError:
        return str(path)

def _download_warning(post_index: int, image_key: str, exc: Exception) -> None:
    print(f"  Warning: skipped image {post_index}/{image_key}: {exc.__class__.__name__}", file=sys.stderr)

def download_image(url: str, images_dir: Path, output_dir: Path, post_index: int, image_key: str) -> Optional[str]:
    safe = safe_url(url)
    parsed = urlparse(safe or "")
    ext = Path(parsed.path).suffix.lower() or ".jpg"
    if not safe or ext not in IMAGE_EXTENSIONS or not host_matches(parsed.hostname or "", _image_host_suffixes()):
        return None
    filepath = images_dir / f"post_{post_index:04d}_{image_key}{ext}"
    try:
        images_dir.mkdir(parents=True, exist_ok=True)
        if images_dir.is_symlink():
            raise ValueError("images directory must not be a symlink")
        if filepath.exists():
            return _relative(filepath, output_dir)
        with requests.get(safe, timeout=30, stream=True) as resp:
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
            size = int(resp.headers.get("Content-Length", "0") or 0)
            if ctype and ctype not in IMAGE_TYPES:
                raise ValueError("unexpected image content type")
            if size > MAX_IMAGE_BYTES:
                raise ValueError("image exceeds max size")
            written = 0
            tmp = filepath.with_suffix(filepath.suffix + ".partial")
            with tmp.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    written += len(chunk)
                    if written > MAX_IMAGE_BYTES:
                        raise ValueError("image exceeds max size")
                    f.write(chunk)
            os.replace(tmp, filepath)
        return _relative(filepath, output_dir)
    except (OSError, ValueError, requests.RequestException) as exc:
        _download_warning(post_index, image_key, exc)
        return None

def format_timestamp(iso_str: object) -> str:
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return md_label(iso_str)

def image_line(url: str, images: bool, images_dir: Optional[Path], output_dir: Path, index: int, key: str) -> Optional[str]:
    src = download_image(url, images_dir, output_dir, index, key) if images and images_dir else url
    return f"![img]({md_url(src)})" if src else None

def _repost_author(repost: dict) -> str:
    user = repost.get("user") or {}
    return user.get("screenName") or user.get("username") or "unknown"

def post_to_markdown(post: dict, index: int, download_images: bool = False, images_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> str:
    output_dir = output_dir or Path.cwd()
    lines = [f"### {index}. {format_timestamp(post.get('createdAt', ''))}", ""]
    topic = (post.get("topic") or {}).get("content")
    if topic:
        lines += [f"> Topic: **{md_label(topic)}**", ""]
    repost = post.get("target") if post.get("type") == "REPOST" else None
    if repost:
        lines += [f"*Repost from @{md_label(_repost_author(repost))}*", ""]
    if post.get("content"):
        lines += [md_text(post.get("content")), ""]
    for i, url in enumerate(extract_pictures(post), 1):
        line = image_line(url, download_images, images_dir, output_dir, index, f"orig_{i}")
        if line:
            lines.append(line)
    link = extract_link(post)
    if link:
        lines += ["", f"[{md_label(link['title'])}]({md_url(link['url'])})"]
    if repost:
        lines += ["", f"> **@{md_label(_repost_author(repost))}**:"]
        lines += ["> " + md_text(line) for line in clean(repost.get("content")).split("\n") if line]
        for i, url in enumerate(extract_pictures(repost), 1):
            line = image_line(url, download_images, images_dir, output_dir, index, f"repost_{i}")
            if line:
                lines.append("> " + line)
        r_link = extract_link(repost)
        if r_link:
            lines.append(f"> [{md_label(r_link['title'])}]({md_url(r_link['url'])})")
    lines += ["", f"`ID: {md_label(post.get('id', ''))}`", "", "---", ""]
    return "\n".join(lines)

def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)

def export_to_markdown(posts: list[dict], user_info: dict, output_path: str, download_images: bool = False, images_dir: Optional[Path] = None) -> None:
    sorted_posts = sorted(posts, key=lambda p: p.get("createdAt", ""))
    output_dir = Path.cwd() if output_path == "-" else Path(output_path).resolve().parent
    lines = [
        f"# {md_text(user_info.get('screenName', ''))} (@{md_label(user_info.get('username', ''))}) - Jike Posts Export",
        "",
        f"**Bio**: {md_text(user_info.get('bio', ''))}",
        f"**Total posts**: {len(sorted_posts)}",
        f"**Exported at**: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "---",
        "",
    ]
    lines += [post_to_markdown(p, i, download_images, images_dir, output_dir) for i, p in enumerate(sorted_posts, 1)]
    content = "\n".join(lines)
    if output_path == "-":
        sys.stdout.write(content)
    else:
        atomic_write(Path(output_path), content)
        print(f"Exported {len(sorted_posts)} posts to {output_path}", file=sys.stderr)
