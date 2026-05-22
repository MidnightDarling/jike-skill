---
name: jike-repo-guide
description: >
  Interact with Jike (即刻) social network — QR login, feed reading, posting,
  commenting, searching, user profile lookup, notifications, and full-history
  export. Use when an agent needs to:
  (1) Log into Jike via QR code scan, (2) Read following/discovery feeds,
  (3) Create, read, or delete posts, (4) Add or remove comments,
  (5) Search content or users, (6) Check notifications, (7) Export Jike history.
  Triggers on: "jike", "即刻", "刷即刻", "发即刻", "jike feed", "jike post".
---

# Jike Skill

## Task

Enable AI agents to interact with the Jike social network: browse feeds, post,
comment, search, and check notifications. Auth is QR scan (no passwords).

## Process

### 0. Install As A Codex Plugin

When the user asks how to install or enable this repository for Codex, use the
Codex plugin marketplace route:

```bash
codex plugin marketplace add MidnightDarling/jike-skill
codex plugin marketplace upgrade jike-skill
```

Then ask the user to fully restart Codex, open `/plugins`, and confirm that
`Jike` from `jike-skill` is installed and enabled. A successful Codex install
loads the packaged skill from:

```text
~/.codex/plugins/cache/jike-skill/jike/<version>/skills/jike/SKILL.md
```

Do not rely on this root `SKILL.md` alone for Codex plugin discovery. It is
useful documentation, but Codex loads the installed plugin copy from its
marketplace cache.

### 1. Authenticate

Run `scripts/auth.py` — user scans the QR with Jike app:

```bash
python3 scripts/auth.py
```

QR rendering depends on the optional `qrcode[pil]` extra:

- **If `qrcode` is installed**: a temporary HTML page (PNG embedded as
  base64) is written to a unique tempfile and its `file://` URI is
  printed — open it in a browser to scan. The same QR is also rendered
  as ASCII to stderr as a fallback. The HTML file is created with mode
  `0o600` and **automatically removed** when the auth flow exits.
- **If `qrcode` is not installed**: the raw `jike://` URL is printed for
  manual scanning. Install with `pip install jike-skill[qr]`.

Outputs JSON with `access_token` and `refresh_token` to stdout. Prefer
`python3 scripts/auth.py --out tokens.json` when saving tokens to disk; it
creates or overwrites the file with owner-only `0600` permissions.

Prefer environment variables for subsequent commands:

```bash
export JIKE_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
export JIKE_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"
```

Avoid passing tokens as `--access-token` / `--refresh-token` except for short
local debugging; command-line arguments can be visible to other same-host users.

### 2. Interact

Prefer the installed `jike` CLI when available, or run `scripts/client.py` from
the repository checkout. The scripts are thin wrappers around the packaged
implementation.

```bash
# Browse feed
jike feed
python3 scripts/client.py feed

# Post
jike post --content "Hello"
python3 scripts/client.py post --content "Hello"

# Post with optional topic IDs and link metadata
jike post --content "Hello" --topic-ids TOPIC_ID \
  --link-title "Example" --link-url "https://example.com"

# Search
jike search --keyword "AI"
python3 scripts/client.py search --keyword "AI"

# User profile
jike profile --username "someone"
python3 scripts/client.py profile --username "someone"
```

### 3. Token Lifecycle

- All commands auto-refresh on 401 (transparent to caller)
- If refresh fails, re-run `jike auth` or `scripts/auth.py`
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
| `export` | Export post history | `--username`, `--json-dump` |

### 4. Export All Posts

Run `jike export` or `scripts/export.py` to export a user's entire post history
to Markdown:

```bash
jike export --username USERNAME \
  --output posts.md --download-images --json-dump

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
| `--checkpoint` | Write resumable pagination checkpoint JSON |
| `--resume` | Resume from `--checkpoint` |

The export automatically:
- Paginates through all posts (rate-limited)
- Preserves images (inline URLs or downloaded with size/type checks)
- Includes repost/share content with original author
- Sorts chronologically (oldest first)
- Includes topic tags and link attachments
- Escapes Markdown/HTML-sensitive content from server responses
- Restricts downloaded images to known Jike-related host suffixes unless
  `JIKE_EXPORT_IMAGE_HOSTS` is set with additional comma-separated suffixes
- Can checkpoint long exports page-by-page and resume after interruption

## Bundled Resources

- **scripts/auth.py** — Repository wrapper for QR auth
- **scripts/client.py** — Repository wrapper for API operations
- **scripts/export.py** — Repository wrapper for Markdown export
- **references/api.md** — Complete API endpoint reference (read when needed)

## API Reference

For endpoint details, headers, and request/response formats:
see [references/api.md](references/api.md).

## Security

- No password auth — QR scan only (same as Jike web)
- All requests require `Origin: https://web.okjike.com` header
- Tokens auto-refresh; only `refresh_token` needs persistence
- QR HTML page is written to an unpredictable tempfile path (no symlink
  TOCTOU window), with `0o600` permissions on POSIX, and is removed
  before the auth flow returns. Caption text is HTML-escaped.
