from dataclasses import dataclass
from typing import Any, TypedDict

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
IMAGE_HOST_SUFFIXES = ("okjike.com", "ruguoapp.com", "jellow.site")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str

    def to_dict(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }


class UserInfo(TypedDict, total=False):
    id: str
    username: str
    screenName: str
    bio: str


class PictureInfo(TypedDict, total=False):
    picUrl: str
    middlePicUrl: str
    thumbnailUrl: str


class LinkInfo(TypedDict, total=False):
    title: str
    linkUrl: str


class JikePost(TypedDict, total=False):
    id: str
    type: str
    content: str
    createdAt: str
    user: UserInfo
    pictures: list[PictureInfo]
    linkInfo: LinkInfo
    target: dict[str, Any]


class JikeResponse(TypedDict, total=False):
    success: bool
    data: Any
    user: UserInfo
    loadMoreKey: Any
    error: str


def host_matches(hostname: str, suffixes: tuple[str, ...]) -> bool:
    host = hostname.lower().strip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)
