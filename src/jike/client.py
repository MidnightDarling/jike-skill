"""
Jike API Client
Feed, posts, comments, search, profiles, notifications.

Author: Claude Opus 4.5
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

from .types import API_BASE, DEFAULT_HEADERS, REQUEST_TIMEOUT_SEC, TokenPair


class JikeClient:
    """Jike API client with automatic token refresh on 401."""

    def __init__(self, tokens: TokenPair):
        self._tokens = tokens

    @property
    def tokens(self) -> TokenPair:
        return self._tokens

    def _headers(self) -> dict:
        return {
            **DEFAULT_HEADERS,
            "Content-Type": "application/json",
            "x-jike-access-token": self._tokens.access_token,
        }

    def _request(
        self, method: str, path: str, retry_on_401: bool = True, **kwargs
    ) -> dict:
        resp = requests.request(
            method,
            f"{API_BASE}{path}",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT_SEC,
            **kwargs,
        )

        if resp.status_code == 401 and retry_on_401:
            self._refresh()
            return self._request(method, path, retry_on_401=False, **kwargs)

        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _refresh(self) -> None:
        resp = requests.post(
            f"{API_BASE}/app_auth_tokens.refresh",
            headers={
                **DEFAULT_HEADERS,
                "Content-Type": "application/json",
                "x-jike-refresh-token": self._tokens.refresh_token,
            },
            json={},
            timeout=REQUEST_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        self._tokens = TokenPair(
            access_token=resp.headers.get(
                "x-jike-access-token", self._tokens.access_token
            ),
            refresh_token=resp.headers.get(
                "x-jike-refresh-token", self._tokens.refresh_token
            ),
        )

    # ── Feed ──────────────────────────────────────────────

    def feed(self, limit: int = 20, load_more_key: Optional[str] = None) -> dict:
        body: dict[str, object] = {"limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request(
            "POST", "/1.0/personalUpdate/followingUpdates", json=body
        )

    # ── Posts ─────────────────────────────────────────────

    def get_post(self, post_id: str) -> dict:
        return self._request("GET", f"/1.0/originalPosts/get?id={post_id}")

    def create_post(self, content: str, picture_keys: Optional[list] = None) -> dict:
        return self._request(
            "POST",
            "/1.0/originalPosts/create",
            json={"content": content, "pictureKeys": picture_keys or []},
        )

    def delete_post(self, post_id: str) -> dict:
        return self._request(
            "POST", "/1.0/originalPosts/remove", json={"id": post_id}
        )

    # ── Comments ──────────────────────────────────────────

    def add_comment(self, post_id: str, content: str) -> dict:
        return self._request(
            "POST",
            "/1.0/comments/add",
            json={
                "targetType": "ORIGINAL_POST",
                "targetId": post_id,
                "content": content,
                "syncToPersonalUpdates": False,
                "pictureKeys": [],
                "force": False,
            },
        )

    def delete_comment(self, comment_id: str) -> dict:
        return self._request(
            "POST",
            "/1.0/comments/remove",
            json={"id": comment_id, "targetType": "ORIGINAL_POST"},
        )

    # ── Search ────────────────────────────────────────────

    def search(
        self, keyword: str, limit: int = 20, load_more_key: Optional[str] = None
    ) -> dict:
        body: dict[str, object] = {"keyword": keyword, "limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/search/integrate", json=body)

    # ── User Posts ──────────────────────────────────────────

    def user_posts(
        self, username: str, limit: int = 20, load_more_key: Optional[str] = None
    ) -> dict:
        body: dict[str, object] = {"username": username, "limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/userPost/listMore", json=body)

    # ── Users ─────────────────────────────────────────────

    def profile(self, username: str) -> dict:
        return self._request("GET", f"/1.0/users/profile?username={username}")

    def followers(self, user_id: str, load_more_key: Optional[str] = None) -> dict:
        body: dict[str, object] = {"userId": user_id}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request(
            "POST", "/1.0/userRelation/getFollowerList", json=body
        )

    def following(self, user_id: str, load_more_key: Optional[str] = None) -> dict:
        body: dict[str, object] = {"userId": user_id}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request(
            "POST", "/1.0/userRelation/getFollowingList", json=body
        )

    # ── Notifications ─────────────────────────────────────

    def unread_notifications(self) -> dict:
        return self._request("GET", "/1.0/notifications/unread")

    def list_notifications(self, load_more_key: Optional[str] = None) -> dict:
        body: dict[str, object] = {}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/notifications/list", json=body)


# ── CLI ───────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jike API client")
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

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("feed")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--load-more-key")

    p = sub.add_parser("post")
    p.add_argument("--content", required=True)
    p.add_argument("--picture-keys", nargs="*", default=[])

    p = sub.add_parser("delete-post")
    p.add_argument("--post-id", required=True)

    p = sub.add_parser("comment")
    p.add_argument("--post-id", required=True)
    p.add_argument("--content", required=True)

    p = sub.add_parser("delete-comment")
    p.add_argument("--comment-id", required=True)

    p = sub.add_parser("search")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("profile")
    p.add_argument("--username", required=True)

    p = sub.add_parser("user-posts")
    p.add_argument("--username", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--load-more-key")

    sub.add_parser("notifications")

    return parser


_DISPATCH = {
    "feed": lambda c, a: c.feed(a.limit, a.load_more_key),
    "post": lambda c, a: c.create_post(a.content, a.picture_keys),
    "delete-post": lambda c, a: c.delete_post(a.post_id),
    "comment": lambda c, a: c.add_comment(a.post_id, a.content),
    "delete-comment": lambda c, a: c.delete_comment(a.comment_id),
    "search": lambda c, a: c.search(a.keyword, a.limit),
    "profile": lambda c, a: c.profile(a.username),
    "user-posts": lambda c, a: c.user_posts(a.username, a.limit, getattr(a, "load_more_key", None)),
    "notifications": lambda c, _: {
        "unread": c.unread_notifications(),
        "list": c.list_notifications(),
    },
}


def main() -> None:
    """CLI entry point for API operations."""
    args = _build_parser().parse_args()
    client = JikeClient(TokenPair(args.access_token, args.refresh_token))

    handler = _DISPATCH.get(args.command)
    if not handler:
        print("Unknown command", file=sys.stderr)
        sys.exit(1)

    try:
        result = handler(client, args)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    except requests.RequestException as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
