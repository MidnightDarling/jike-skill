# jike-skill

Jike (即刻) client for humans and AI agents.
QR login (browser HTML or terminal ASCII), full feed/post/comment/search
API, and one-command export of your entire Jike history to Markdown.

即刻社交网络客户端 — 给人用，也给 AI agent 用。
扫码登录支持浏览器 HTML 与终端 ASCII 双通道；一行命令导出全部即刻历史。

**Current version**: `0.4.0` — see [CHANGELOG.md](CHANGELOG.md) for details.

## Install / 安装

```bash
pip install jike-skill          # core
pip install jike-skill[qr]      # + browser HTML & terminal ASCII QR rendering
```

The `[qr]` extra pulls in `qrcode[pil]`. Without it, `jike auth` falls
back to printing the raw `jike://` URL for manual scanning.

## Quick Start / 快速开始

### CLI

```bash
# 1. Login — open the browser HTML QR (or scan the ASCII fallback in the terminal)
# 1. 登录 — 浏览器打开 HTML 二维码（或扫终端里的 ASCII 备用 QR）
jike auth

# 2. Set tokens as env vars (recommended) / 推荐用环境变量传 token
export JIKE_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
export JIKE_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"

# 3. Browse your feed / 刷关注流
jike feed

# 4. Search / 搜索
jike search --keyword "AI"

# 5. Post something / 发一条即刻
jike post --content "Hello world"
```

### Python

```python
from jike import JikeClient, TokenPair, authenticate

# First time: QR login
tokens = authenticate()

# Then use the client
client = JikeClient(tokens)
feed = client.feed(limit=20)
client.create_post(content="Hello from Python")
results = client.search(keyword="AI")
profile = client.profile(username="someone")
```

### Codex Plugin

Codex does not automatically use a public repository just because it contains a
`SKILL.md`. Add this repository as a plugin marketplace, restart Codex, then
install or enable the plugin from `/plugins`.

```bash
# One-time setup: add this public repository as a Codex plugin marketplace
codex plugin marketplace add MidnightDarling/jike-skill
```

After restarting Codex:

```text
/plugins
```

Choose **Jike Skill Codex Plugins** and confirm that **Jike** is installed and
enabled. Codex then loads the packaged skill from `skills/jike/SKILL.md`.

### Claude Code Plugin

```bash
# Option A: Plugin marketplace (one-time setup)
/plugin marketplace add MidnightDarling/jike-skill
/plugin install jike@jike-skill

# Option B: Manual copy (clone and place the whole repo as a skill folder)
git clone https://github.com/MidnightDarling/jike-skill.git ~/.claude/skills/jike

# Option C: Quick use (no install, just read)
# Send this to any Claude Code session:
Read https://github.com/MidnightDarling/jike-skill/blob/main/SKILL.md
```

Codex 需要先把公开仓库加为 plugin marketplace，再在 `/plugins` 里安装或启用；
Claude Code 则可以用插件一键装、手动复制文件夹到 `~/.claude/skills/`、或直接发
链接临时用。

## All Commands / 全部命令

| Command | What it does | 功能 |
|---------|-------------|------|
| `jike auth` | QR login, print tokens | 扫码登录 |
| `jike feed` | Following feed | 关注流 |
| `jike post` | Create a post | 发帖 |
| `jike delete-post` | Delete a post | 删帖 |
| `jike comment` | Comment on a post | 评论 |
| `jike delete-comment` | Delete a comment | 删评论 |
| `jike search` | Search content | 搜索 |
| `jike profile` | User profile | 用户资料 |
| `jike user-posts` | List a user's posts | 用户帖子列表 |
| `jike notifications` | Check notifications | 查看通知 |

## Export All Posts / 导出全部帖子

```bash
# Export to Markdown (with image URLs inline)
# 导出为 Markdown（图片以 URL 内联）
python3 scripts/export.py --username YOUR_USERNAME

# Export with local images + raw JSON backup
# 导出并下载图片 + JSON 原始数据备份
python3 scripts/export.py --username YOUR_USERNAME \
  --output my_posts.md --download-images --json-dump
```

Both commands use `JIKE_ACCESS_TOKEN` and `JIKE_REFRESH_TOKEN` if flags are omitted.

Features / 功能:
- Paginates through ALL posts automatically / 自动翻页获取全部帖子
- Includes images (URLs or downloaded) / 包含图片
- Preserves reposts with original author / 保留转发内容和原作者
- Chronological order / 按时间排序
- Topic tags and links / 包含话题标签和链接

## How Auth Works / 认证原理

No passwords. Jike uses QR-code scan authentication (same as their web client):

不用密码。即刻用的是 QR 扫码认证（和它的网页版一样）：

1. Create a session on Jike's server → get a `uuid`
2. Encode the uuid into a `jike://` deep-link QR code
3. User scans QR with Jike app → app confirms the session
4. Server returns `access_token` + `refresh_token`
5. `refresh_token` has long validity — save it, skip QR next time

### QR rendering (v0.4.0+)

When `qrcode[pil]` is installed, the QR is rendered through **two
independent channels** — either may individually fail without breaking
the other:

- **Browser HTML** — a self-contained HTML page (PNG embedded as
  base64) is written to an unpredictable tempfile path with `0o600`
  permissions on POSIX, and its `file://` URI is printed to stderr.
  The file is removed automatically when the auth flow returns.
- **Terminal ASCII** — the same QR is also printed to stderr for
  terminals that can render it.

If `qrcode` is not installed, the raw `jike://` URL is printed instead
so it can be scanned out-of-band.

二选一，互不影响：装了 `qrcode` 就同时给浏览器 HTML 与终端 ASCII；
没装就直接打印 `jike://` 原始链接，手动扫描。

## Architecture / 项目结构

```
jike-skill/
├── SKILL.md                   # Legacy root skill definition
├── CHANGELOG.md               # Version history
├── scripts/                   # Standalone scripts (agent runs these)
│   ├── auth.py                # QR authentication
│   ├── client.py              # API client CLI
│   └── export.py              # Full history export to Markdown
├── references/
│   └── api.md                 # API endpoint reference (loaded on demand)
├── .agents/plugins/
│   └── marketplace.json       # Codex repo marketplace catalog
├── .codex-plugin/
│   └── plugin.json            # Codex plugin manifest
├── .claude-plugin/            # Plugin marketplace metadata
│   ├── marketplace.json       # Marketplace catalog
│   └── plugin.json            # Plugin manifest
├── skills/
│   └── jike/
│       └── SKILL.md           # Codex packaged skill entrypoint
├── pyproject.toml             # Python packaging (pip installable)
└── src/jike/                  # Python package (for pip users)
    ├── __init__.py
    ├── __main__.py
    ├── types.py
    ├── auth.py
    └── client.py
```

## Design / 设计

- **Dual-mode** — Works as a `pip install` package and as an AI-agent plugin
- **Frozen dataclasses** — `TokenPair` is immutable; refresh returns new instances
- **Auto-retry on 401** — Token refresh is transparent to the caller
- **Progressive disclosure** — SKILL.md is lean; API details in `references/api.md`
- **Zero config** — No passwords, no API keys, just scan and go

## Acknowledgments / 致谢

This project is a from-scratch rewrite inspired by [joway/jike-skill](https://github.com/joway/jike-skill),
whose reverse-engineering of Jike's web API endpoints made this work possible.
The original repository documented the QR authentication flow and API surface
through HAR capture analysis — we built on that research with a typed Python package,
proper separation of concerns, and dual-mode distribution (pip + Claude Code skill).

本项目受 [joway/jike-skill](https://github.com/joway/jike-skill) 启发，从零重写。
原作者通过抓包逆向工程了即刻 Web 端的 API，为本项目提供了关键的接口研究基础。
在此基础上，我们用类型化 Python 包、关注点分离和双模式分发（pip + Claude Code skill）重新实现了全部功能。

Thanks also to [@imHw](https://github.com/imHw) for opening
[PR #1](https://github.com/MidnightDarling/jike-skill/pull/1), which
surfaced the terminal-QR truncation issue that motivated the v0.4.0
browser-HTML rendering path.

## Contributors / 贡献者

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/MidnightDarling">
        <img src="https://github.com/MidnightDarling.png?size=96" width="64" height="64" alt="MidnightDarling avatar"><br>
        <sub><b>MidnightDarling</b></sub>
      </a><br>
      <sub>Owner and steward</sub>
    </td>
    <td align="center">
      <a href="https://github.com/claude">
        <img src="https://github.com/claude.png?size=96" width="64" height="64" alt="Claude avatar"><br>
        <sub><b>Claude Opus</b></sub>
      </a><br>
      <sub>Core package and QR flow</sub>
    </td>
    <td align="center">
      <a href="https://github.com/codex">
        <img src="https://github.com/codex.png?size=96" width="64" height="64" alt="GPT-5 avatar"><br>
        <sub><b>GPT-5</b></sub>
      </a><br>
      <sub>Security hardening and Codex plugin packaging</sub>
    </td>
    <td align="center">
      <a href="https://github.com/imHw">
        <img src="https://github.com/imHw.png?size=96" width="64" height="64" alt="imHw avatar"><br>
        <sub><b>imHw</b></sub>
      </a><br>
      <sub>PR #1 issue discovery</sub>
    </td>
  </tr>
</table>

GitHub's external Contributors panel is driven by commit metadata. The
GPT-authored plugin work uses `GPT-5 <codex@openai.com>`, which resolves to
the [`@codex`](https://github.com/codex) GitHub avatar.

---

Authors:
- **Claude Opus 4.5** — v0.1.0 (initial release), v0.2.0 (export)
- **Claude Opus 4.6** — v0.2.1 (API migration)
- **GPT-5** — v0.3.0 (security hardening, env var tokens, timeouts)
- **Claude Opus 4.7** — v0.4.0 (secure browser-HTML QR login)

License: MIT
