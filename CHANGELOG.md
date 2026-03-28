# Changelog

All notable changes to jike-skill will be documented in this file.

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
