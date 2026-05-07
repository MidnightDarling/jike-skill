# Changelog

All notable changes to jike-skill will be documented in this file.

## Unreleased

### Added

- Codex plugin packaging via `.codex-plugin/plugin.json`,
  `.agents/plugins/marketplace.json`, and `skills/jike/SKILL.md`, so the public
  repository can be added as a Codex plugin marketplace. The Codex marketplace
  entry is marked `INSTALLED_BY_DEFAULT` for direct use after the marketplace is
  added.

### Changed

- README now documents the Codex marketplace install flow separately from the
  Claude Code plugin flow.
- `.claude-plugin/marketplace.json` now uses a `./`-prefixed source path for
  compatibility with Codex marketplace path rules.
- `.agents/plugins/marketplace.json` now uses a Git-backed root source for
  Codex, avoiding the empty local-path resolution produced by `./`.

## [0.4.0] - 2026-04-25

### Added

- **Browser-friendly QR login**: when `qrcode[pil]` is installed, a
  self-contained HTML page (PNG embedded as base64) is written and its
  `file://` URI is printed — useful when terminal width truncates the
  ASCII QR. ASCII output remains available as a fallback.
- **`QRRender` dataclass**: `render_qr()` now returns a structured
  result describing which channel(s) succeeded (`html_path`,
  `ascii_printed`).
- New unit tests covering QR HTML mode bits, HTML cleanup on success
  and timeout, caption HTML-escaping, and channel independence
  (HTML failure does not block ASCII and vice versa).

### Security

- **QR HTML uses an unpredictable tempfile path** via
  `tempfile.NamedTemporaryFile`, eliminating the symlink/TOCTOU window
  that a fixed `/tmp/jike_qr_login.html` would expose on multi-user
  hosts.
- **Tempfile is created with `0o600`** mode on POSIX so other local
  users cannot read the live login QR during the scan window.
- **`try / finally` cleanup**: the QR HTML file is unlinked when the
  auth flow returns (success, timeout, or exception).
- **HTML-escape user-controlled caption** before interpolation, so a
  malformed UUID cannot break out of the HTML page.

### Fixed

- **Robust error handling in `render_qr`**: `OSError`,
  `UnicodeEncodeError`, and other I/O failures are caught per-channel
  and downgraded to a structured fallback instead of crashing the
  entire auth flow.
- **Cross-platform tempdir**: HTML page now respects
  `tempfile.gettempdir()` instead of hard-coding `/tmp`, so the auth
  flow no longer breaks on Windows.
- **Single QR matrix**: HTML and ASCII reuse a single `QRCode`
  instance instead of building two with mismatched `box_size` settings.

### Changed

- Plugin metadata (`.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`) bumped from `0.1.0` to `0.4.0`,
  closing the long-standing drift behind `pyproject.toml`.
- Package `__version__` and `__all__` updated to expose `render_qr`
  and `QRRender`.
- `.gitignore` now excludes macOS `._*` resource forks that appear when
  the working tree lives on an exFAT/SMB volume.

## [0.3.0] - 2026-03-28

### Added

- **Environment variable tokens**: `JIKE_ACCESS_TOKEN` and `JIKE_REFRESH_TOKEN` — CLI flags become optional when env vars are set
- **Request timeouts**: all HTTP calls enforce `REQUEST_TIMEOUT_SEC = 15` to prevent indefinite hangs
- **Long-poll timeout**: QR scan polling uses dedicated `POLL_REQUEST_TIMEOUT_SEC = 60` to accommodate server hold behavior
- **User posts command**: `user-posts` subcommand with `--username`, `--limit`, `--load-more-key`

### Fixed

- **API endpoint**: restored `/1.0/userPost/listMore` across all modules (previous `personalUpdate/single` workaround no longer needed)
- **Token refresh fallback**: standalone scripts now fall back to previous token on missing headers (was empty string)
- **CLI error handling**: all entry points catch `requests.RequestException` instead of only `HTTPError`, covering timeouts and connection errors
- **Test isolation**: `test_missing_*_token_raises` now clears env vars via `monkeypatch.delenv` to prevent false passes in CI

### Changed

- Updated README with env-var-first workflow and revised examples
- Updated SKILL.md with timeout and environment variable documentation
- Added export artifact patterns to `.gitignore`

## [0.2.1] - 2026-02-26

### Fixed

- **API migration**: `/1.0/userPost/listMore` endpoint removed by Jike (returns 404)
  - Migrated to `/1.0/personalUpdate/single` for user post listing
  - `loadMoreKey` format changed from string to `{"lastId": "<id>"}`
  - Removed unused `limit` parameter (new endpoint returns ~25 posts per page)
- Updated `scripts/export.py`, `scripts/client.py`, and `references/api.md`

### Verified

- Full export tested: 924 posts, pagination working correctly

## [0.2.0] - 2026-02-26

### Added

- **Export**: `scripts/export.py` — export a user's entire post history to Markdown
  - Automatic pagination through all posts
  - Image support (inline URLs or local download via `--download-images`)
  - Repost/share content preserved with original author attribution
  - Topic tags and link attachments included
  - Chronological sort (oldest first)
  - Optional raw JSON dump (`--json-dump`) for backup
- **User posts**: `user-posts` command in both standalone and package clients
- **API**: documented `POST /1.0/userPost/listMore` endpoint in `references/api.md`

### Changed

- Updated README with export section and revised project tree
- Updated SKILL.md with export workflow documentation

## [0.1.0] - 2026-02-01

### Added

- Initial release
- QR code authentication (no passwords)
- Following feed reader
- Post creation and deletion
- Comment creation and deletion
- Content search
- User profile lookup
- Notification checking
- Dual-mode distribution: `pip install` package + Claude Code skill
- Automatic token refresh on 401
- Complete API reference in `references/api.md`
