"""
Command-line interface for Jike API operations.
"""

import argparse
import json
import os
import sys

import requests

from .client import JikeClient
from .types import TokenPair

TARGET_TYPES = ("ORIGINAL_POST", "REPOST")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be positive")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jike API client")
    access_env = os.getenv("JIKE_ACCESS_TOKEN") or None
    refresh_env = os.getenv("JIKE_REFRESH_TOKEN") or None
    parser.add_argument(
        "--access-token",
        default=access_env,
        required=access_env is None,
        help="Access token. Prefer JIKE_ACCESS_TOKEN; flags may be process-visible.",
    )
    parser.add_argument(
        "--refresh-token",
        default=refresh_env,
        required=refresh_env is None,
        help="Refresh token. Prefer JIKE_REFRESH_TOKEN; flags may be process-visible.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("feed")
    p.add_argument("--limit", type=_positive_int, default=20)
    p.add_argument("--load-more-key")
    p = sub.add_parser("post")
    p.add_argument("--content", required=True)
    p.add_argument("--picture-keys", nargs="*", default=[])
    p.add_argument("--topic-ids", nargs="*", default=[])
    p.add_argument("--link-title")
    p.add_argument("--link-url")
    p = sub.add_parser("delete-post")
    p.add_argument("--post-id", required=True)
    p = sub.add_parser("comment")
    p.add_argument("--post-id", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--target-type", default="ORIGINAL_POST", choices=TARGET_TYPES)
    p = sub.add_parser("delete-comment")
    p.add_argument("--comment-id", required=True)
    p.add_argument("--target-type", default="ORIGINAL_POST", choices=TARGET_TYPES)
    p = sub.add_parser("search")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=_positive_int, default=20)
    p.add_argument("--load-more-key")
    p = sub.add_parser("profile")
    p.add_argument("--username", required=True)
    p = sub.add_parser("user-posts")
    p.add_argument("--username", required=True)
    p.add_argument("--limit", type=_positive_int, default=20)
    p.add_argument("--load-more-key")
    p = sub.add_parser("notifications")
    p.add_argument("--load-more-key")
    return parser


def _link_info(args: argparse.Namespace) -> dict[str, str] | None:
    if not args.link_url:
        return None
    return {"title": args.link_title or args.link_url, "linkUrl": args.link_url}


_DISPATCH = {
    "feed": lambda c, a: c.feed(a.limit, a.load_more_key),
    "post": lambda c, a: c.create_post(a.content, a.picture_keys, a.topic_ids, _link_info(a)),
    "delete-post": lambda c, a: c.delete_post(a.post_id),
    "comment": lambda c, a: c.add_comment(a.post_id, a.content, a.target_type),
    "delete-comment": lambda c, a: c.delete_comment(a.comment_id, a.target_type),
    "search": lambda c, a: c.search(a.keyword, a.limit, a.load_more_key),
    "profile": lambda c, a: c.profile(a.username),
    "user-posts": lambda c, a: c.user_posts(a.username, a.limit, a.load_more_key),
    "notifications": lambda c, a: {
        "unread": c.unread_notifications(),
        "list": c.list_notifications(a.load_more_key),
    },
}


def _warn_process_visible_tokens(argv: list[str]) -> None:
    if "--access-token" in argv or "--refresh-token" in argv:
        print(
            "[!] Token flags may be visible to other local users; prefer env vars.",
            file=sys.stderr,
        )


def _safe_error(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        return f"{exc.__class__.__name__}: HTTP {response.status_code}"
    return exc.__class__.__name__


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for API operations."""
    argv = list(sys.argv[1:] if argv is None else argv)
    _warn_process_visible_tokens(argv)
    args = _build_parser().parse_args(argv)
    client = JikeClient(TokenPair(args.access_token, args.refresh_token))
    try:
        result = _DISPATCH[args.command](client, args)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    except requests.RequestException as exc:
        print(json.dumps({"error": _safe_error(exc)}), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(json.dumps({"error": exc.__class__.__name__}), file=sys.stderr)
        sys.exit(1)
