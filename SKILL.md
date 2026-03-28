---
name: jike
description: >
  Interact with Jike (即刻) social network — QR login, feed reading, posting,
  commenting, searching, and user profile lookup. Use when Claude needs to:
  (1) Log into Jike via QR code scan, (2) Read following/discovery feeds,
  (3) Create, read, or delete posts, (4) Add or remove comments,
  (5) Search content or users, (6) Check notifications.
  Triggers on: "jike", "即刻", "刷即刻", "发即刻", "jike feed", "jike post".
---

# Jike Skill

## Task

Enable AI agents to interact with the Jike social network: browse feeds, post,
comment, search, and check notifications. Auth is QR scan (no passwords).

## Process

### 1. Authenticate

Run `scripts/auth.py` — user scans the terminal QR with Jike app:

```bash
python3 scripts/auth.py
```

Outputs JSON with `access_token` and `refresh_token` to stdout.
Save the `refresh_token` for reuse (long validity, avoids re-scanning).

Prefer environment variables for subsequent commands:

```bash
export JIKE_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
export JIKE_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"
```

### 2. Interact

Run `scripts/client.py` with any command:

```bash
# Browse feed
python3 scripts/client.py feed

# Post
python3 scripts/client.py post --content "Hello"

# Search
python3 scripts/client.py search --keyword "AI"

# User profile
python3 scripts/client.py profile --username "someone"
```

### 3. Token Lifecycle

- All commands auto-refresh on 401 (transparent to caller)
- If refresh fails, re-run `scripts/auth.py`
- Only dependency: `requests` (standard, likely already installed)

## Operations

| Command | Description | Key Args |
|---------|-------------|----------|
| `feed` | Following feed | `--limit` |
| `post` | Create post | `--content` |
| `delete-post` | Remove post | `--post-id` |
| `comment` | Comment on post | `--post-id`, `--content` |
| `delete-comment` | Remove comment | `--comment-id` |
| `search` | Search content | `--keyword`, `--limit` |
| `profile` | User profile | `--username` |
| `user-posts` | List user's posts | `--username`, `--limit` |
| `notifications` | Unread + list | — |

### 3. Export All Posts

Run `scripts/export.py` to export a user's entire post history to Markdown:

```bash
python3 scripts/export.py --username USERNAME \
  --output posts.md --download-images --json-dump
```

| Flag | Description |
|------|-------------|
| `--username` | Jike username to export |
| `--output` | Output file (default: `<username>_jike_export.md`) |
| `--download-images` | Download images locally |
| `--images-dir` | Custom directory for images |
| `--json-dump` | Also save raw JSON alongside Markdown |

The export automatically:
- Paginates through all posts (rate-limited)
- Preserves images (inline URLs or downloaded)
- Includes repost/share content with original author
- Sorts chronologically (oldest first)
- Includes topic tags and link attachments

## Bundled Resources

- **scripts/auth.py** — Standalone QR auth, no pip install needed
- **scripts/client.py** — Standalone API client, no pip install needed
- **scripts/export.py** — Full post history export to Markdown
- **references/api.md** — Complete API endpoint reference (read when needed)

## API Reference

For endpoint details, headers, and request/response formats:
see [references/api.md](references/api.md).

## Security

- No password auth — QR scan only (same as Jike web)
- All requests require `Origin: https://web.okjike.com` header
- Tokens auto-refresh; only `refresh_token` needs persistence
