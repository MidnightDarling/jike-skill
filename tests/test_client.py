"""
Tests for jike.client module.

Covers:
- JikeClient construction and properties
- _headers building
- _request with retry on 401
- All API methods: feed, get_post, create_post, delete_post,
  add_comment, delete_comment, search, profile, followers,
  following, unread_notifications, list_notifications
- CLI: _build_parser, _DISPATCH, main

Author: Claude Opus 4.5
"""

import json
import sys
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from jike.client import JikeClient, _build_parser, _DISPATCH, main
from jike.types import API_BASE, TokenPair


# ── JikeClient construction ────────────────────────────────


class TestJikeClientInit:

    def test_stores_tokens(self, token_pair):
        client = JikeClient(token_pair)
        assert client.tokens == token_pair

    def test_tokens_property_returns_token_pair(self, token_pair):
        client = JikeClient(token_pair)
        assert isinstance(client.tokens, TokenPair)

    def test_headers_include_access_token(self, token_pair):
        client = JikeClient(token_pair)
        headers = client._headers()
        assert headers["x-jike-access-token"] == token_pair.access_token

    def test_headers_include_content_type(self, token_pair):
        client = JikeClient(token_pair)
        headers = client._headers()
        assert headers["Content-Type"] == "application/json"

    def test_headers_include_default_headers(self, token_pair):
        client = JikeClient(token_pair)
        headers = client._headers()
        assert "User-Agent" in headers
        assert "Origin" in headers


# ── _request with 401 auto-refresh ─────────────────────────


class TestRequestRetry:

    @patch("jike.client.requests.request")
    @patch("jike.client.requests.post")
    def test_retry_on_401(
        self,
        mock_post,
        mock_request,
        token_pair,
        new_access_token,
        new_refresh_token,
    ):
        # First request returns 401, second returns 200
        mock_401 = MagicMock()
        mock_401.status_code = 401

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.content = b'{"data": "ok"}'
        mock_200.json.return_value = {"data": "ok"}

        mock_request.side_effect = [mock_401, mock_200]

        # Refresh returns new tokens
        mock_refresh_resp = MagicMock()
        mock_refresh_resp.raise_for_status.return_value = None
        mock_refresh_resp.headers = {
            "x-jike-access-token": new_access_token,
            "x-jike-refresh-token": new_refresh_token,
        }
        mock_post.return_value = mock_refresh_resp

        client = JikeClient(token_pair)
        result = client._request("GET", "/test")

        assert result == {"data": "ok"}
        assert client.tokens.access_token == new_access_token
        assert mock_request.call_count == 2

    @patch("jike.client.requests.request")
    @patch("jike.client.requests.post")
    def test_no_infinite_retry_on_401(
        self, mock_post, mock_request, token_pair
    ):
        """After refresh, if still 401, should raise not retry again."""
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = requests.HTTPError("401")
        mock_request.return_value = mock_401

        mock_refresh_resp = MagicMock()
        mock_refresh_resp.raise_for_status.return_value = None
        mock_refresh_resp.headers = {}
        mock_post.return_value = mock_refresh_resp

        client = JikeClient(token_pair)

        with pytest.raises(requests.HTTPError):
            client._request("GET", "/test")

        # Should be called exactly twice: first attempt + retry after refresh
        assert mock_request.call_count == 2

    @patch("jike.client.requests.request")
    def test_no_retry_when_disabled(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"ok": true}'
        mock_resp.json.return_value = {"ok": True}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client._request("GET", "/test", retry_on_401=False)

        assert result == {"ok": True}
        assert mock_request.call_count == 1

    @patch("jike.client.requests.request")
    def test_raises_on_non_401_error(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)

        with pytest.raises(requests.HTTPError):
            client._request("GET", "/test")

    @patch("jike.client.requests.request")
    def test_returns_empty_dict_for_empty_content(
        self, mock_request, token_pair
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client._request("DELETE", "/test")

        assert result == {}


# ── _refresh ────────────────────────────────────────────────


class TestClientRefresh:

    @patch("jike.client.requests.post")
    def test_updates_tokens_after_refresh(
        self,
        mock_post,
        token_pair,
        new_access_token,
        new_refresh_token,
    ):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {
            "x-jike-access-token": new_access_token,
            "x-jike-refresh-token": new_refresh_token,
        }
        mock_post.return_value = mock_resp

        client = JikeClient(token_pair)
        client._refresh()

        assert client.tokens.access_token == new_access_token
        assert client.tokens.refresh_token == new_refresh_token

    @patch("jike.client.requests.post")
    def test_keeps_old_tokens_when_headers_missing(
        self, mock_post, token_pair
    ):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        client = JikeClient(token_pair)
        client._refresh()

        assert client.tokens.access_token == token_pair.access_token
        assert client.tokens.refresh_token == token_pair.refresh_token

    @patch("jike.client.requests.post")
    def test_sends_refresh_token_in_header(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        client = JikeClient(token_pair)
        client._refresh()

        call_kwargs = mock_post.call_args
        headers = call_kwargs[1]["headers"]
        assert headers["x-jike-refresh-token"] == token_pair.refresh_token

    @patch("jike.client.requests.post")
    def test_calls_refresh_endpoint(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        client = JikeClient(token_pair)
        client._refresh()

        url = mock_post.call_args[0][0]
        assert "/app_auth_tokens.refresh" in url

    @patch("jike.client.requests.post")
    def test_raises_on_refresh_failure(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("403")
        mock_post.return_value = mock_resp

        client = JikeClient(token_pair)

        with pytest.raises(requests.HTTPError):
            client._refresh()


# ── API Methods ─────────────────────────────────────────────


class TestFeed:

    @patch("jike.client.requests.request")
    def test_feed_default(self, mock_request, token_pair, mock_feed_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_feed_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.feed()

        assert "data" in result
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/personalUpdate/followingUpdates" in call_args[0][1]

    @patch("jike.client.requests.request")
    def test_feed_with_limit(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.feed(limit=5)

        body = mock_request.call_args[1]["json"]
        assert body["limit"] == 5

    @patch("jike.client.requests.request")
    def test_feed_with_load_more_key(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.feed(load_more_key="next-page")

        body = mock_request.call_args[1]["json"]
        assert body["loadMoreKey"] == "next-page"

    @patch("jike.client.requests.request")
    def test_feed_without_load_more_key(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.feed()

        body = mock_request.call_args[1]["json"]
        assert "loadMoreKey" not in body


class TestGetPost:

    @patch("jike.client.requests.request")
    def test_get_post(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": {"id": "p1"}}'
        mock_resp.json.return_value = {"data": {"id": "p1"}}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.get_post("p1")

        assert result["data"]["id"] == "p1"
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "originalPosts/get" in call_args[0][1]
        assert "id=p1" in call_args[0][1]


class TestCreatePost:

    @patch("jike.client.requests.request")
    def test_create_post(
        self, mock_request, token_pair, mock_post_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_post_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.create_post("Hello world")

        assert "data" in result
        body = mock_request.call_args[1]["json"]
        assert body["content"] == "Hello world"
        assert body["pictureKeys"] == []

    @patch("jike.client.requests.request")
    def test_create_post_with_pictures(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": {}}'
        mock_resp.json.return_value = {"data": {}}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.create_post("With pic", picture_keys=["key1", "key2"])

        body = mock_request.call_args[1]["json"]
        assert body["pictureKeys"] == ["key1", "key2"]


class TestDeletePost:

    @patch("jike.client.requests.request")
    def test_delete_post(
        self, mock_request, token_pair, mock_delete_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_delete_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.delete_post("post-to-delete")

        body = mock_request.call_args[1]["json"]
        assert body["id"] == "post-to-delete"
        assert "originalPosts/remove" in mock_request.call_args[0][1]


class TestAddComment:

    @patch("jike.client.requests.request")
    def test_add_comment(
        self, mock_request, token_pair, mock_comment_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_comment_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.add_comment("post-001", "Nice post!")

        body = mock_request.call_args[1]["json"]
        assert body["targetType"] == "ORIGINAL_POST"
        assert body["targetId"] == "post-001"
        assert body["content"] == "Nice post!"
        assert body["syncToPersonalUpdates"] is False
        assert body["pictureKeys"] == []
        assert body["force"] is False


class TestDeleteComment:

    @patch("jike.client.requests.request")
    def test_delete_comment(
        self, mock_request, token_pair, mock_delete_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_delete_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.delete_comment("comment-001")

        body = mock_request.call_args[1]["json"]
        assert body["id"] == "comment-001"
        assert body["targetType"] == "ORIGINAL_POST"


class TestSearch:

    @patch("jike.client.requests.request")
    def test_search(
        self, mock_request, token_pair, mock_search_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_search_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.search("test keyword")

        body = mock_request.call_args[1]["json"]
        assert body["keyword"] == "test keyword"
        assert body["limit"] == 20
        assert "loadMoreKey" not in body

    @patch("jike.client.requests.request")
    def test_search_with_pagination(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.search("query", limit=10, load_more_key="page2")

        body = mock_request.call_args[1]["json"]
        assert body["limit"] == 10
        assert body["loadMoreKey"] == "page2"


class TestProfile:

    @patch("jike.client.requests.request")
    def test_profile(
        self, mock_request, token_pair, mock_profile_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_profile_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.profile("testuser")

        assert "user" in result
        url = mock_request.call_args[0][1]
        assert "username=testuser" in url


class TestFollowers:

    @patch("jike.client.requests.request")
    def test_followers(
        self, mock_request, token_pair, mock_followers_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_followers_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.followers("user-001")

        body = mock_request.call_args[1]["json"]
        assert body["userId"] == "user-001"
        assert "loadMoreKey" not in body

    @patch("jike.client.requests.request")
    def test_followers_with_pagination(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.followers("user-001", load_more_key="next")

        body = mock_request.call_args[1]["json"]
        assert body["loadMoreKey"] == "next"


class TestFollowing:

    @patch("jike.client.requests.request")
    def test_following(
        self, mock_request, token_pair, mock_following_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_following_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.following("user-001")

        body = mock_request.call_args[1]["json"]
        assert body["userId"] == "user-001"

    @patch("jike.client.requests.request")
    def test_following_with_pagination(self, mock_request, token_pair):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.following("user-001", load_more_key="page2")

        body = mock_request.call_args[1]["json"]
        assert body["loadMoreKey"] == "page2"


class TestNotifications:

    @patch("jike.client.requests.request")
    def test_unread_notifications(
        self, mock_request, token_pair, mock_unread_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_unread_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.unread_notifications()

        assert result["data"]["count"] == 3
        url = mock_request.call_args[0][1]
        assert "/notifications/unread" in url

    @patch("jike.client.requests.request")
    def test_list_notifications(
        self, mock_request, token_pair, mock_notifications_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_notifications_response
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        result = client.list_notifications()

        assert "data" in result
        body = mock_request.call_args[1]["json"]
        assert "loadMoreKey" not in body

    @patch("jike.client.requests.request")
    def test_list_notifications_with_pagination(
        self, mock_request, token_pair
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data": []}'
        mock_resp.json.return_value = {"data": []}
        mock_request.return_value = mock_resp

        client = JikeClient(token_pair)
        client.list_notifications(load_more_key="notif-page2")

        body = mock_request.call_args[1]["json"]
        assert body["loadMoreKey"] == "notif-page2"


# ── CLI Parser ──────────────────────────────────────────────


class TestBuildParser:

    def test_feed_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r", "feed"
        ])
        assert args.command == "feed"
        assert args.limit == 20
        assert args.load_more_key is None

    def test_feed_with_options(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "feed", "--limit", "5", "--load-more-key", "next",
        ])
        assert args.limit == 5
        assert args.load_more_key == "next"

    def test_post_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "post", "--content", "Hello",
        ])
        assert args.command == "post"
        assert args.content == "Hello"
        assert args.picture_keys == []

    def test_post_with_pictures(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "post", "--content", "Pic", "--picture-keys", "k1", "k2",
        ])
        assert args.picture_keys == ["k1", "k2"]

    def test_delete_post_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "delete-post", "--post-id", "p1",
        ])
        assert args.command == "delete-post"
        assert args.post_id == "p1"

    def test_comment_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "comment", "--post-id", "p1", "--content", "Nice",
        ])
        assert args.command == "comment"
        assert args.post_id == "p1"
        assert args.content == "Nice"

    def test_delete_comment_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "delete-comment", "--comment-id", "c1",
        ])
        assert args.command == "delete-comment"
        assert args.comment_id == "c1"

    def test_search_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "search", "--keyword", "python",
        ])
        assert args.command == "search"
        assert args.keyword == "python"
        assert args.limit == 20

    def test_profile_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "profile", "--username", "alice",
        ])
        assert args.command == "profile"
        assert args.username == "alice"

    def test_notifications_command(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--access-token", "a", "--refresh-token", "r",
            "notifications",
        ])
        assert args.command == "notifications"

    def test_tokens_from_environment(self, monkeypatch):
        monkeypatch.setenv("JIKE_ACCESS_TOKEN", "env-a")
        monkeypatch.setenv("JIKE_REFRESH_TOKEN", "env-r")
        parser = _build_parser()
        args = parser.parse_args(["feed"])
        assert args.access_token == "env-a"
        assert args.refresh_token == "env-r"
        assert args.command == "feed"

    def test_missing_access_token_raises(self, monkeypatch):
        monkeypatch.delenv("JIKE_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("JIKE_REFRESH_TOKEN", raising=False)
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--refresh-token", "r", "feed"])

    def test_missing_refresh_token_raises(self, monkeypatch):
        monkeypatch.delenv("JIKE_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("JIKE_REFRESH_TOKEN", raising=False)
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--access-token", "a", "feed"])

    def test_missing_command_raises(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--access-token", "a", "--refresh-token", "r"
            ])


class TestDispatch:

    def test_all_commands_registered(self):
        expected = {
            "feed", "post", "delete-post", "comment",
            "delete-comment", "search", "profile", "user-posts", "notifications",
        }
        assert set(_DISPATCH.keys()) == expected

    def test_each_dispatch_is_callable(self):
        for cmd, handler in _DISPATCH.items():
            assert callable(handler), f"{cmd} handler is not callable"


class TestClientMain:

    @patch("jike.client.requests.request")
    def test_main_feed(self, mock_request, capsys, mock_feed_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_feed_response
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            ["jike", "--access-token", "a", "--refresh-token", "r", "feed"],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "data" in output

    @patch("jike.client.requests.request")
    def test_main_search(self, mock_request, capsys, mock_search_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_search_response
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            [
                "jike", "--access-token", "a", "--refresh-token", "r",
                "search", "--keyword", "test",
            ],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "data" in output

    @patch("jike.client.requests.request")
    def test_main_post(self, mock_request, capsys, mock_post_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_post_response
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            [
                "jike", "--access-token", "a", "--refresh-token", "r",
                "post", "--content", "Hello from test",
            ],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "data" in output

    @patch("jike.client.requests.request")
    def test_main_http_error_exits(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            ["jike", "--access-token", "a", "--refresh-token", "r", "feed"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    @patch("jike.client.requests.request")
    def test_main_profile(self, mock_request, capsys, mock_profile_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_profile_response
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            [
                "jike", "--access-token", "a", "--refresh-token", "r",
                "profile", "--username", "alice",
            ],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "user" in output

    @patch("jike.client.requests.request")
    def test_main_delete_post(
        self, mock_request, capsys, mock_delete_response
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_delete_response
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            [
                "jike", "--access-token", "a", "--refresh-token", "r",
                "delete-post", "--post-id", "p1",
            ],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True

    @patch("jike.client.requests.request")
    def test_main_notifications(self, mock_request, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = {"data": {"count": 0}}
        mock_request.return_value = mock_resp

        with patch(
            "sys.argv",
            [
                "jike", "--access-token", "a", "--refresh-token", "r",
                "notifications",
            ],
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "unread" in output
        assert "list" in output
