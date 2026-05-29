"""
Tests for jike.__main__ module.

Covers:
- CLI dispatcher routing (auth, feed, etc.)
- Missing subcommand error handling

Author: Claude Opus 4.5
"""

from unittest.mock import patch

import pytest

from jike.__main__ import main


class TestMainDispatch:

    def test_no_args_prints_usage_and_exits(self, capsys):
        with patch("sys.argv", ["jike"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Usage:" in captured.err

    @patch("jike.__main__.sys.argv", ["jike", "auth"])
    def test_auth_command_dispatches_to_auth_main(self):
        with patch("jike.auth.main") as mock_auth_main:
            main()
            mock_auth_main.assert_called_once_with([])

    @patch("jike.__main__.sys.argv", ["jike", "auth", "--extra-flag"])
    def test_auth_strips_auth_from_argv(self):
        with patch("jike.auth.main") as mock_auth_main:
            main()
            mock_auth_main.assert_called_once_with(["--extra-flag"])

    @patch("jike.__main__.sys.argv", ["jike", "feed"])
    def test_non_auth_dispatches_to_client_main(self):
        with patch("jike.client_cli.main") as mock_client_main:
            main()
            mock_client_main.assert_called_once_with(["feed"])

    @patch("jike.__main__.sys.argv", ["jike", "search"])
    def test_search_dispatches_to_client_main(self):
        with patch("jike.client_cli.main") as mock_client_main:
            main()
            mock_client_main.assert_called_once_with(["search"])

    @patch("jike.__main__.sys.argv", ["jike", "post"])
    def test_post_dispatches_to_client_main(self):
        with patch("jike.client_cli.main") as mock_client_main:
            main()
            mock_client_main.assert_called_once_with(["post"])

    @patch("jike.__main__.sys.argv", ["jike", "profile"])
    def test_profile_dispatches_to_client_main(self):
        with patch("jike.client_cli.main") as mock_client_main:
            main()
            mock_client_main.assert_called_once_with(["profile"])

    @patch("jike.__main__.sys.argv", ["jike", "export", "--username", "alice"])
    def test_export_dispatches_to_export_main(self):
        with patch("jike.export.main") as mock_export_main:
            main()
            mock_export_main.assert_called_once_with(["--username", "alice"])

    @patch("jike.__main__.sys.argv", ["jike", "--help"])
    def test_help_flag_lists_all_commands(self, capsys):
        main()
        out = capsys.readouterr().out
        assert "auth" in out
        assert "export" in out
        assert "feed" in out
