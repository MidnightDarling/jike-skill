"""
jike — Jike social network client for humans and AI agents.

Author: Claude Opus 4.5 (v0.1) · Claude Opus 4.7 (v0.4)
"""

from .auth import QRRender, authenticate, refresh_tokens, render_qr
from .client import JikeClient
from .types import TokenPair

__all__ = [
    "JikeClient",
    "QRRender",
    "TokenPair",
    "authenticate",
    "refresh_tokens",
    "render_qr",
]
__version__ = "0.4.0"
