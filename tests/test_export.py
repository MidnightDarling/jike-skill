"""
Tests for Jike export hardening.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jike.export import fetch_all_posts, fetch_user_profile
from jike.export_utils import (
    download_image,
    export_to_markdown,
    json_path_for,
    post_to_markdown,
    validate_username,
)


def test_validate_username_rejects_path_traversal():
    with pytest.raises(ValueError):
        validate_username("../../etc/passwd")


def test_json_path_uses_suffix_replacement():
    assert json_path_for("notes.md.backup", "alice") == Path("notes.md.json")


@patch("jike.export.requests.request")
def test_fetch_user_profile_quotes_username(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"user": {}}'
    mock_resp.json.return_value = {"user": {}}
    mock_request.return_value = mock_resp

    fetch_user_profile("alice&admin=true", "a", "r")

    url = mock_request.call_args[0][1]
    assert "username=alice%26admin%3Dtrue" in url


@patch("jike.export.time.sleep")
@patch("jike.export.requests.request")
def test_fetch_user_profile_retries_once_on_429(mock_request, mock_sleep):
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "3"}
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.content = b'{"user": {}}'
    mock_200.json.return_value = {"user": {}}
    mock_request.side_effect = [mock_429, mock_200]

    result, _, _ = fetch_user_profile("alice", "a", "r")

    assert result == {"user": {}}
    mock_sleep.assert_called_once_with(3.0)
    assert mock_request.call_count == 2


def test_post_to_markdown_escapes_html_and_filters_bad_links():
    post = {
        "id": "</sub><script>x</script>",
        "createdAt": "not-a-date<script>",
        "content": "<script>alert(1)</script>|pipe",
        "linkInfo": {"title": "bad", "linkUrl": "javascript:alert(1)"},
        "pictures": [{"picUrl": "data:text/html,evil"}],
    }

    markdown = post_to_markdown(post, 1)

    assert "<script>" not in markdown
    assert "&lt;script&gt;" in markdown
    assert "\\|pipe" in markdown
    assert "javascript:" not in markdown
    assert "data:text" not in markdown


def test_export_to_markdown_writes_atomically(tmp_path):
    output = tmp_path / "posts.txt"

    export_to_markdown([], {"screenName": "Alice", "username": "alice"}, str(output))

    assert output.exists()
    assert not (tmp_path / "posts.txt.partial").exists()
    assert "Jike Posts Export" in output.read_text(encoding="utf-8")


@patch("jike.export_utils.requests.get")
def test_download_image_rejects_disallowed_extension(mock_get, tmp_path):
    result = download_image(
        "https://cdn.example.com/payload.svg",
        tmp_path / "images",
        tmp_path,
        1,
        "orig_1",
    )

    assert result is None
    mock_get.assert_not_called()


@patch("jike.export_utils.requests.get")
def test_download_image_rejects_disallowed_host(mock_get, tmp_path):
    result = download_image(
        "https://evil.example.com/payload.png",
        tmp_path / "images",
        tmp_path,
        1,
        "orig_1",
    )

    assert result is None
    mock_get.assert_not_called()


@patch("jike.export_utils.requests.get")
def test_download_image_allows_jike_cdn_host(mock_get, tmp_path):
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.headers = {"Content-Type": "image/png", "Content-Length": "3"}
    mock_resp.iter_content.return_value = [b"abc"]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = download_image(
        "https://cdn.ruguoapp.com/payload.png",
        tmp_path / "images",
        tmp_path,
        1,
        "orig_1",
    )

    assert result == "images/post_0001_orig_1.png"
    assert (tmp_path / result).read_bytes() == b"abc"


@patch("jike.export.fetch_user_posts")
def test_fetch_all_posts_writes_checkpoint(mock_fetch, tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    mock_fetch.side_effect = [
        ({"data": [{"id": "1"}], "loadMoreKey": {"lastId": "1"}}, "a", "r"),
        ({"data": [{"id": "2"}]}, "a", "r"),
    ]

    posts, _, _ = fetch_all_posts("alice", "a", "r", checkpoint_path=checkpoint)

    assert [post["id"] for post in posts] == ["1", "2"]
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert saved["username"] == "alice"
    assert saved["posts"] == posts
    assert saved["loadMoreKey"] is None


@patch("jike.export.fetch_user_posts")
def test_fetch_all_posts_resumes_from_checkpoint(mock_fetch, tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps({"username": "alice", "posts": [{"id": "1"}], "loadMoreKey": {"lastId": "1"}}),
        encoding="utf-8",
    )
    mock_fetch.return_value = ({"data": [{"id": "2"}]}, "a", "r")

    posts, _, _ = fetch_all_posts("alice", "a", "r", checkpoint_path=checkpoint, resume=True)

    assert [post["id"] for post in posts] == ["1", "2"]
    assert mock_fetch.call_args.kwargs["load_more_key"] == {"lastId": "1"}
