# jike-skill

Jike (即刻) client for humans and AI agents.
One-command export of your entire Jike history to Markdown.

即刻社交网络客户端 — 给人用，也给 AI agent 用。
一行命令导出你的全部即刻历史。

## Install / 安装

```bash
pip install jike-skill          # core
pip install jike-skill[qr]      # + terminal QR code rendering
```

## Quick Start / 快速开始

### CLI

```bash
# 1. Login — scan the QR code with Jike app
# 1. 登录 — 用即刻 App 扫描终端里的二维码
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

三种方式都行：插件一键装、手动复制文件夹到 `~/.claude/skills/`、或直接发链接临时用。

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

## Architecture / 项目结构

```
jike-skill/                    # Copy this whole folder to ~/.claude/skills/jike/
├── SKILL.md                   # Skill definition (Claude reads this)
├── CHANGELOG.md               # Version history
├── scripts/                   # Standalone scripts (agent runs these)
│   ├── auth.py                # QR authentication
│   ├── client.py              # API client CLI
│   └── export.py              # Full history export to Markdown
├── references/
│   └── api.md                 # API endpoint reference (loaded on demand)
├── .claude-plugin/            # Plugin marketplace metadata
│   ├── marketplace.json       # Marketplace catalog
│   └── plugin.json            # Plugin manifest
├── pyproject.toml             # Python packaging (pip installable)
└── src/jike/                  # Python package (for pip users)
    ├── __init__.py
    ├── __main__.py
    ├── types.py
    ├── auth.py
    └── client.py
```

## Design / 设计

- **Dual-mode** — Works as a `pip install` package AND a Claude Code skill
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

---

Author: **Claude Opus 4.5** (v0.1.0), **Claude Opus 4.6** (v0.2.0), **GPT-5 Codex** (security hardening & docs)
License: MIT
