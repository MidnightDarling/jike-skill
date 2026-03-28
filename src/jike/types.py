"""
Shared types for the Jike client.

Author: Claude Opus 4.5
"""

from dataclasses import dataclass

API_BASE = "https://api.ruguoapp.com"
REQUEST_TIMEOUT_SEC = 15

DEFAULT_HEADERS = {
    "Origin": "https://web.okjike.com",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "DNT": "1",
}


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str

    def to_dict(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }
