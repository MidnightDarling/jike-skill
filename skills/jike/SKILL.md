---
name: jike
description: >
  Interact with Jike (即刻) from Codex: QR login, feed reading, posting,
  commenting, searching, profile lookup, notifications, and full-history export.
  Use when the user mentions Jike, 即刻, 刷即刻, 发即刻, jike feed, jike post,
  or exporting Jike history.
---

# Jike

## Task

Use the Jike social network client from this plugin or from the installed
`jike-skill` Python package. Authentication is QR scan only; do not ask for or
store passwords.

## Paths

When working from a plugin checkout, resolve bundled files from the plugin root:

- `scripts/auth.py` for QR login
- `scripts/client.py` for feed, post, comment, search, profile, and notifications
- `scripts/export.py` for full-history Markdown export
- `references/api.md` for endpoint details

If this skill file is the current reference point, the plugin root is two
directories above it.

## Install This Plugin In Codex

When the user asks how to install or enable this skill for Codex, use the
Codex plugin marketplace route:

```bash
codex plugin marketplace add MidnightDarling/jike-skill
codex plugin marketplace upgrade jike-skill
```

Then ask the user to fully restart Codex, open `/plugins`, and confirm that
`Jike` from `jike-skill` is installed and enabled. In a running Codex
environment, verify success by checking that the installed skill exists under:

```text
~/.codex/plugins/cache/jike-skill/jike/<version>/skills/jike/SKILL.md
```

Do not treat the public repository's root `SKILL.md` as enough for Codex
plugin discovery. Codex loads the packaged plugin from the marketplace cache.

## Authenticate

Prefer the installed CLI when available:

```bash
jike auth
```

From a repository or plugin checkout, run:

```bash
python3 scripts/auth.py
```

The command prints JSON containing `access_token` and `refresh_token`. Ask the
user to scan the QR code with the Jike app. For later commands, prefer
environment variables:

```bash
export JIKE_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
export JIKE_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"
```

## Interact

Use the installed CLI:

```bash
jike feed --limit 20
jike search --keyword "AI" --limit 20
jike post --content "Hello"
jike profile --username "someone"
jike notifications
```

Or use the bundled script from the plugin root:

```bash
python3 scripts/client.py feed --limit 20
python3 scripts/client.py search --keyword "AI" --limit 20
python3 scripts/client.py post --content "Hello"
python3 scripts/client.py profile --username "someone"
python3 scripts/client.py notifications
```

## Export

Export a user's post history to Markdown:

```bash
python3 scripts/export.py --username USERNAME \
  --output posts.md --download-images --json-dump
```

The export paginates through available posts, preserves images, includes repost
or share content, sorts chronologically, and can save raw JSON beside the
Markdown output.

## Safety

- Never hardcode or commit Jike tokens.
- Prefer `JIKE_ACCESS_TOKEN` and `JIKE_REFRESH_TOKEN` for command execution.
- If token refresh fails, re-run QR authentication.
- Read `references/api.md` before changing endpoint behaviour.
