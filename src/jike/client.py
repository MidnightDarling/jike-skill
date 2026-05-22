import time
from threading import Lock
from typing import Callable, Optional
from urllib.parse import quote

import requests

from .types import API_BASE, DEFAULT_HEADERS, JikeResponse, REQUEST_TIMEOUT_SEC, TokenPair

TokenCallback = Callable[[TokenPair], None]

def _quoted(value: str) -> str:
    return quote(str(value), safe="")

def _retry_after(resp: requests.Response) -> float:
    try:
        return min(max(float(resp.headers.get("Retry-After", "1")), 0), 30)
    except ValueError:
        return 1.0

class JikeClient:
    def __init__(
        self,
        tokens: TokenPair,
        on_tokens_changed: Optional[TokenCallback] = None,
    ):
        self._tokens = tokens
        self._on_tokens_changed = on_tokens_changed
        self._refresh_lock = Lock()

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
        self,
        method: str,
        path: str,
        retry_on_401: bool = True,
        retry_on_429: bool = True,
        **kwargs,
    ) -> JikeResponse:
        resp = requests.request(
            method,
            f"{API_BASE}{path}",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT_SEC,
            **kwargs,
        )
        if resp.status_code == 401 and retry_on_401:
            self._refresh(previous_access_token=self._tokens.access_token)
            return self._request(method, path, retry_on_401=False, **kwargs)
        if resp.status_code == 429 and retry_on_429:
            time.sleep(_retry_after(resp))
            return self._request(method, path, retry_on_429=False, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _refresh(self, previous_access_token: Optional[str] = None) -> None:
        with self._refresh_lock:
            if previous_access_token and self._tokens.access_token != previous_access_token:
                return
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
                access_token=resp.headers.get("x-jike-access-token", self._tokens.access_token),
                refresh_token=resp.headers.get("x-jike-refresh-token", self._tokens.refresh_token),
            )
            if self._on_tokens_changed:
                self._on_tokens_changed(self._tokens)

    def feed(self, limit: int = 20, load_more_key: Optional[str] = None) -> JikeResponse:
        body: dict[str, object] = {"limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/personalUpdate/followingUpdates", json=body)

    def get_post(self, post_id: str) -> JikeResponse:
        return self._request("GET", f"/1.0/originalPosts/get?id={_quoted(post_id)}")

    def create_post(
        self,
        content: str,
        picture_keys: Optional[list[str]] = None,
        topic_ids: Optional[list[str]] = None,
        link_info: Optional[dict[str, str]] = None,
    ) -> JikeResponse:
        body: dict[str, object] = {"content": content, "pictureKeys": picture_keys or []}
        if topic_ids:
            body["topicIds"] = topic_ids
        if link_info:
            body["linkInfo"] = link_info
        return self._request(
            "POST",
            "/1.0/originalPosts/create",
            json=body,
        )

    def delete_post(self, post_id: str) -> JikeResponse:
        return self._request("POST", "/1.0/originalPosts/remove", json={"id": post_id})

    def add_comment(
        self,
        post_id: str,
        content: str,
        target_type: str = "ORIGINAL_POST",
    ) -> JikeResponse:
        return self._request(
            "POST",
            "/1.0/comments/add",
            json={
                "targetType": target_type,
                "targetId": post_id,
                "content": content,
                "syncToPersonalUpdates": False,
                "pictureKeys": [],
                "force": False,
            },
        )

    def delete_comment(
        self,
        comment_id: str,
        target_type: str = "ORIGINAL_POST",
    ) -> JikeResponse:
        return self._request(
            "POST",
            "/1.0/comments/remove",
            json={"id": comment_id, "targetType": target_type},
        )

    def search(
        self,
        keyword: str,
        limit: int = 20,
        load_more_key: Optional[str] = None,
    ) -> JikeResponse:
        body: dict[str, object] = {"keyword": keyword, "limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/search/integrate", json=body)

    def user_posts(
        self,
        username: str,
        limit: int = 20,
        load_more_key: Optional[str] = None,
    ) -> JikeResponse:
        body: dict[str, object] = {"username": username, "limit": limit}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/userPost/listMore", json=body)

    def profile(self, username: str) -> JikeResponse:
        return self._request(
            "GET",
            f"/1.0/users/profile?username={_quoted(username)}",
        )

    def followers(self, user_id: str, load_more_key: Optional[str] = None) -> JikeResponse:
        body: dict[str, object] = {"userId": user_id}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/userRelation/getFollowerList", json=body)

    def following(self, user_id: str, load_more_key: Optional[str] = None) -> JikeResponse:
        body: dict[str, object] = {"userId": user_id}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/userRelation/getFollowingList", json=body)

    def unread_notifications(self) -> JikeResponse:
        return self._request("GET", "/1.0/notifications/unread")

    def list_notifications(self, load_more_key: Optional[str] = None) -> JikeResponse:
        body: dict[str, object] = {}
        if load_more_key:
            body["loadMoreKey"] = load_more_key
        return self._request("POST", "/1.0/notifications/list", json=body)
