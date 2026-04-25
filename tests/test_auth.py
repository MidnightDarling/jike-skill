"""
Tests for jike.auth module.

Covers:
- create_session
- build_qr_payload (URL encoding)
- render_qr (qrcode missing, secure HTML output, channel independence)
- _write_qr_html (tempfile permissions, html.escape)
- _extract_tokens (body x-jike, body access_token, headers)
- poll_confirmation (success, timeout, request exceptions)
- refresh_tokens
- authenticate (full flow, HTML cleanup on success and timeout)
- auth CLI main

Author: Claude Opus 4.5 · Claude Opus 4.7 (v0.4 secure QR HTML)
"""

import json
import os
import stat
import sys
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from jike.auth import (
    POLL_INTERVAL_SEC,
    POLL_TIMEOUT_SEC,
    QRRender,
    _extract_tokens,
    _write_qr_html,
    authenticate,
    build_qr_payload,
    create_session,
    main,
    poll_confirmation,
    refresh_tokens,
    render_qr,
)
from jike.types import TokenPair


# ── create_session ──────────────────────────────────────────


class TestCreateSession:

    @patch("jike.auth.requests.post")
    def test_returns_uuid(self, mock_post, mock_session_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_session_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        uuid = create_session()

        assert uuid == "test-uuid-1234-abcd"

    @patch("jike.auth.requests.post")
    def test_calls_correct_endpoint(self, mock_post, mock_session_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_session_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        create_session()

        call_args = mock_post.call_args
        assert "/sessions.create" in call_args[0][0]

    @patch("jike.auth.requests.post")
    def test_raises_on_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        mock_post.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            create_session()

    @patch("jike.auth.requests.post")
    def test_sends_content_type_header(self, mock_post, mock_session_response):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_session_response
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        create_session()

        call_kwargs = mock_post.call_args
        headers = call_kwargs[1]["headers"]
        assert headers["Content-Type"] == "application/json"


# ── build_qr_payload ───────────────────────────────────────


class TestBuildQrPayload:

    def test_starts_with_jike_deeplink(self):
        payload = build_qr_payload("uuid-123")
        assert payload.startswith("jike://page.jk/web?url=")

    def test_contains_encoded_scan_url(self):
        payload = build_qr_payload("uuid-123")
        expected_scan = "https://www.okjike.com/account/scan?uuid=uuid-123"
        encoded = urllib.parse.quote(expected_scan, safe="")
        assert encoded in payload

    def test_ends_with_display_flags(self):
        payload = build_qr_payload("uuid-123")
        assert payload.endswith(
            "&displayHeader=false&displayFooter=false"
        )

    def test_url_encoding_special_chars(self):
        """Ensure colons and slashes in the scan URL are percent-encoded."""
        payload = build_qr_payload("uuid-123")
        # After "url=", the scan URL should be fully encoded
        url_part = payload.split("url=")[1].split("&displayHeader")[0]
        assert ":" not in url_part
        assert "/" not in url_part

    def test_uuid_preserved_in_payload(self):
        payload = build_qr_payload("my-special-uuid")
        decoded = urllib.parse.unquote(payload)
        assert "my-special-uuid" in decoded


# ── render_qr ───────────────────────────────────────────────


class TestRenderQr:

    def test_returns_empty_render_when_qrcode_missing(self):
        with patch.dict(sys.modules, {"qrcode": None}):
            result = render_qr("test-data")
            assert isinstance(result, QRRender)
            assert result.html_path is None
            assert result.ascii_printed is False
            assert result.any_visible is False

    def test_returns_render_with_html_and_ascii_when_qrcode_available(self):
        with patch.dict(sys.modules, {"qrcode": MagicMock()}):
            result = render_qr("test-data", caption="uuid-xyz")

        assert isinstance(result, QRRender)
        assert result.ascii_printed is True
        assert result.html_path is not None
        try:
            assert result.html_path.exists()
            assert result.html_path.suffix == ".html"
        finally:
            result.html_path.unlink(missing_ok=True)

    def test_html_failure_does_not_block_ascii(self):
        with patch.dict(sys.modules, {"qrcode": MagicMock()}), \
             patch("jike.auth._write_qr_html", side_effect=OSError("disk full")):
            result = render_qr("test-data", caption="uuid-xyz")

        assert result.html_path is None
        assert result.ascii_printed is True
        assert result.any_visible is True

    def test_ascii_failure_does_not_block_html(self):
        qr_module = MagicMock()
        # The QRCode instance returned by qrcode.QRCode() is what owns print_ascii
        qr_instance = MagicMock()
        qr_instance.print_ascii.side_effect = UnicodeEncodeError(
            "ascii", "", 0, 1, "bad encoding"
        )
        qr_module.QRCode.return_value = qr_instance

        with patch.dict(sys.modules, {"qrcode": qr_module}):
            result = render_qr("test-data", caption="uuid-xyz")

        assert result.ascii_printed is False
        assert result.html_path is not None
        try:
            assert result.html_path.exists()
        finally:
            result.html_path.unlink(missing_ok=True)


class TestWriteQrHtml:

    def test_creates_unique_tempfile(self):
        path_a = _write_qr_html("AAAA", caption="cap-a")
        path_b = _write_qr_html("BBBB", caption="cap-b")
        try:
            assert path_a != path_b
            assert path_a.exists()
            assert path_b.exists()
        finally:
            path_a.unlink(missing_ok=True)
            path_b.unlink(missing_ok=True)

    @pytest.mark.skipif(os.name != "posix", reason="POSIX-only mode bits")
    def test_tempfile_is_owner_only_readable(self):
        path = _write_qr_html("png-data", caption="cap")
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            # tempfile.NamedTemporaryFile (mkstemp) creates with 0o600 on POSIX
            assert mode == 0o600
        finally:
            path.unlink(missing_ok=True)

    def test_caption_is_html_escaped(self):
        path = _write_qr_html("png", caption="<script>alert('x')</script>")
        try:
            content = path.read_text(encoding="utf-8")
            assert "<script>alert" not in content
            assert "&lt;script&gt;" in content
        finally:
            path.unlink(missing_ok=True)

    def test_path_can_be_opened_as_file_uri(self):
        path = _write_qr_html("png", caption="cap")
        try:
            uri = path.as_uri()
            assert uri.startswith("file://")
        finally:
            path.unlink(missing_ok=True)


# ── _extract_tokens ─────────────────────────────────────────


class TestExtractTokens:

    def test_from_body_xjike_keys(
        self, access_token, refresh_token, mock_tokens_in_body
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_tokens_in_body
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is not None
        assert result.access_token == access_token
        assert result.refresh_token == refresh_token

    def test_from_body_alt_keys(
        self, access_token, refresh_token, mock_tokens_in_body_alt
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_tokens_in_body_alt
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is not None
        assert result.access_token == access_token
        assert result.refresh_token == refresh_token

    def test_from_headers(self, access_token, refresh_token):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.headers = {
            "x-jike-access-token": access_token,
            "x-jike-refresh-token": refresh_token,
        }

        result = _extract_tokens(mock_resp)

        assert result is not None
        assert result.access_token == access_token
        assert result.refresh_token == refresh_token

    def test_body_takes_priority_over_headers(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "x-jike-access-token": "body-access",
            "x-jike-refresh-token": "body-refresh",
        }
        mock_resp.headers = {
            "x-jike-access-token": "header-access",
            "x-jike-refresh-token": "header-refresh",
        }

        result = _extract_tokens(mock_resp)

        assert result.access_token == "body-access"
        assert result.refresh_token == "body-refresh"

    def test_returns_none_when_no_tokens(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is None

    def test_returns_none_when_only_access(self, access_token):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "x-jike-access-token": access_token,
        }
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is None

    def test_returns_none_when_only_refresh(self, refresh_token):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "x-jike-refresh-token": refresh_token,
        }
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is None

    def test_handles_json_decode_error(self):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON")
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert result is None

    def test_returns_token_pair_type(self, mock_tokens_in_body):
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_tokens_in_body
        mock_resp.headers = {}

        result = _extract_tokens(mock_resp)

        assert isinstance(result, TokenPair)

    def test_mixed_body_and_header_sources(self, access_token, refresh_token):
        """Access in body, refresh in header."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "x-jike-access-token": access_token,
        }
        mock_resp.headers = {
            "x-jike-refresh-token": refresh_token,
        }

        result = _extract_tokens(mock_resp)

        assert result is not None
        assert result.access_token == access_token
        assert result.refresh_token == refresh_token


# ── poll_confirmation ───────────────────────────────────────


class TestPollConfirmation:

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_returns_tokens_on_200(
        self, mock_get, mock_sleep, mock_tokens_in_body
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_tokens_in_body
        mock_resp.headers = {}
        mock_get.return_value = mock_resp

        result = poll_confirmation("uuid-123")

        assert result is not None
        assert isinstance(result, TokenPair)

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_returns_none_on_timeout(self, mock_get, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_get.return_value = mock_resp

        result = poll_confirmation("uuid-123")

        assert result is None

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_retries_on_400(self, mock_get, mock_sleep, mock_tokens_in_body):
        mock_400 = MagicMock()
        mock_400.status_code = 400

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = mock_tokens_in_body
        mock_200.headers = {}

        mock_get.side_effect = [mock_400, mock_400, mock_200]

        result = poll_confirmation("uuid-123")

        assert result is not None
        assert mock_get.call_count == 3

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_retries_on_request_exception(
        self, mock_get, mock_sleep, mock_tokens_in_body
    ):
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = mock_tokens_in_body
        mock_200.headers = {}

        mock_get.side_effect = [
            requests.ConnectionError("network down"),
            mock_200,
        ]

        result = poll_confirmation("uuid-123")

        assert result is not None
        assert mock_get.call_count == 2

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_sleeps_between_polls(self, mock_get, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_get.return_value = mock_resp

        poll_confirmation("uuid-123")

        for call in mock_sleep.call_args_list:
            assert call[0][0] == POLL_INTERVAL_SEC

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_calls_correct_endpoint(self, mock_get, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "x-jike-access-token": "a",
            "x-jike-refresh-token": "r",
        }
        mock_resp.headers = {}
        mock_get.return_value = mock_resp

        poll_confirmation("uuid-xyz")

        url = mock_get.call_args[0][0]
        assert "sessions.wait_for_confirmation" in url
        assert "uuid=uuid-xyz" in url

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_max_attempts_calculated_correctly(
        self, mock_get, mock_sleep
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_get.return_value = mock_resp

        poll_confirmation("uuid-123")

        expected_attempts = POLL_TIMEOUT_SEC // POLL_INTERVAL_SEC
        assert mock_get.call_count == expected_attempts

    @patch("jike.auth.time.sleep")
    @patch("jike.auth.requests.get")
    def test_retries_on_other_status_codes(
        self, mock_get, mock_sleep, mock_tokens_in_body
    ):
        mock_500 = MagicMock()
        mock_500.status_code = 500

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = mock_tokens_in_body
        mock_200.headers = {}

        mock_get.side_effect = [mock_500, mock_200]

        result = poll_confirmation("uuid-123")

        assert result is not None


# ── refresh_tokens ──────────────────────────────────────────


class TestRefreshTokens:

    @patch("jike.auth.requests.post")
    def test_returns_new_token_pair(
        self, mock_post, token_pair, new_access_token, new_refresh_token
    ):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {
            "x-jike-access-token": new_access_token,
            "x-jike-refresh-token": new_refresh_token,
        }
        mock_post.return_value = mock_resp

        result = refresh_tokens(token_pair)

        assert result.access_token == new_access_token
        assert result.refresh_token == new_refresh_token

    @patch("jike.auth.requests.post")
    def test_falls_back_to_old_tokens(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        result = refresh_tokens(token_pair)

        assert result.access_token == token_pair.access_token
        assert result.refresh_token == token_pair.refresh_token

    @patch("jike.auth.requests.post")
    def test_sends_refresh_token_header(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        refresh_tokens(token_pair)

        call_kwargs = mock_post.call_args
        headers = call_kwargs[1]["headers"]
        assert headers["x-jike-refresh-token"] == token_pair.refresh_token

    @patch("jike.auth.requests.post")
    def test_calls_refresh_endpoint(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        refresh_tokens(token_pair)

        url = mock_post.call_args[0][0]
        assert "/app_auth_tokens.refresh" in url

    @patch("jike.auth.requests.post")
    def test_raises_on_http_error(self, mock_post, token_pair):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("403")
        mock_post.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            refresh_tokens(token_pair)

    @patch("jike.auth.requests.post")
    def test_returns_immutable_token_pair(
        self, mock_post, token_pair, new_access_token, new_refresh_token
    ):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.headers = {
            "x-jike-access-token": new_access_token,
            "x-jike-refresh-token": new_refresh_token,
        }
        mock_post.return_value = mock_resp

        result = refresh_tokens(token_pair)

        assert isinstance(result, TokenPair)
        import dataclasses
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.access_token = "mutated"


# ── authenticate (full flow) ───────────────────────────────


class TestAuthenticate:

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_full_flow_success(
        self,
        mock_create,
        mock_render,
        mock_poll,
        mock_refresh,
        token_pair,
    ):
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=None, ascii_printed=True)
        mock_poll.return_value = token_pair
        mock_refresh.return_value = token_pair

        result = authenticate()

        assert result == token_pair
        mock_create.assert_called_once()
        mock_poll.assert_called_once_with("uuid-abc")
        mock_refresh.assert_called_once_with(token_pair)

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_exits_on_timeout(
        self, mock_create, mock_render, mock_poll, mock_refresh
    ):
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=None, ascii_printed=True)
        mock_poll.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            authenticate()

        assert exc_info.value.code == 1
        mock_refresh.assert_not_called()

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_prints_qr_payload_when_no_qr_visible(
        self,
        mock_create,
        mock_render,
        mock_poll,
        mock_refresh,
        token_pair,
        capsys,
    ):
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=None, ascii_printed=False)
        mock_poll.return_value = token_pair
        mock_refresh.return_value = token_pair

        authenticate()

        captured = capsys.readouterr()
        assert "jike://page.jk/web" in captured.err

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_prints_html_uri_when_html_rendered(
        self,
        mock_create,
        mock_render,
        mock_poll,
        mock_refresh,
        token_pair,
        capsys,
        tmp_path,
    ):
        html_file = tmp_path / "qr.html"
        html_file.write_text("<html/>", encoding="utf-8")
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=html_file, ascii_printed=True)
        mock_poll.return_value = token_pair
        mock_refresh.return_value = token_pair

        authenticate()

        captured = capsys.readouterr()
        assert "QR HTML" in captured.err
        assert html_file.as_uri() in captured.err

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_html_file_is_cleaned_up_on_success(
        self,
        mock_create,
        mock_render,
        mock_poll,
        mock_refresh,
        token_pair,
        tmp_path,
    ):
        html_file = tmp_path / "qr.html"
        html_file.write_text("<html/>", encoding="utf-8")
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=html_file, ascii_printed=True)
        mock_poll.return_value = token_pair
        mock_refresh.return_value = token_pair

        authenticate()

        assert not html_file.exists()

    @patch("jike.auth.refresh_tokens")
    @patch("jike.auth.poll_confirmation")
    @patch("jike.auth.render_qr")
    @patch("jike.auth.create_session")
    def test_html_file_is_cleaned_up_on_timeout(
        self,
        mock_create,
        mock_render,
        mock_poll,
        mock_refresh,
        tmp_path,
    ):
        html_file = tmp_path / "qr.html"
        html_file.write_text("<html/>", encoding="utf-8")
        mock_create.return_value = "uuid-abc"
        mock_render.return_value = QRRender(html_path=html_file, ascii_printed=True)
        mock_poll.return_value = None  # timeout

        with pytest.raises(SystemExit):
            authenticate()

        assert not html_file.exists()


# ── auth main (CLI) ────────────────────────────────────────


class TestAuthMain:

    @patch("jike.auth.authenticate")
    def test_prints_json_tokens(
        self, mock_auth, token_pair, capsys
    ):
        mock_auth.return_value = token_pair

        main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["access_token"] == token_pair.access_token
        assert output["refresh_token"] == token_pair.refresh_token
