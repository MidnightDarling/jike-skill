"""
Shared fixtures for jike test suite.

Author: Claude Opus 4.5
"""

import pytest

from jike.types import TokenPair


# ── Token fixtures ───────────────────────────────────────────

@pytest.fixture
def access_token():
    return "fake-access-token-for-tests"


@pytest.fixture
def refresh_token():
    return "fake-refresh-token-for-tests"


@pytest.fixture
def token_pair(access_token, refresh_token):
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@pytest.fixture
def new_access_token():
    return "fake-new-access-token-for-tests"


@pytest.fixture
def new_refresh_token():
    return "fake-new-refresh-token-for-tests"


# ── Mock response factories ──────────────────────────────────

@pytest.fixture
def mock_session_response():
    """Response from /sessions.create."""
    return {"uuid": "test-uuid-1234-abcd"}


@pytest.fixture
def mock_tokens_in_body(access_token, refresh_token):
    """Tokens returned in JSON body (x-jike- prefix keys)."""
    return {
        "x-jike-access-token": access_token,
        "x-jike-refresh-token": refresh_token,
    }


@pytest.fixture
def mock_tokens_in_body_alt(access_token, refresh_token):
    """Tokens returned in JSON body (access_token/refresh_token keys)."""
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@pytest.fixture
def mock_feed_response():
    """Typical feed response."""
    return {
        "data": [
            {
                "id": "post-001",
                "type": "ORIGINAL_POST",
                "content": "Hello Jike!",
                "user": {"username": "testuser"},
            }
        ],
        "loadMoreKey": "next-page-key",
    }


@pytest.fixture
def mock_post_response():
    """Response from creating a post."""
    return {
        "data": {
            "id": "post-new-001",
            "type": "ORIGINAL_POST",
            "content": "Test post content",
        }
    }


@pytest.fixture
def mock_comment_response():
    """Response from adding a comment."""
    return {
        "data": {
            "id": "comment-001",
            "content": "Test comment",
            "targetId": "post-001",
        }
    }


@pytest.fixture
def mock_search_response():
    """Response from search endpoint."""
    return {
        "data": [
            {"id": "result-001", "content": "Search result"}
        ],
        "loadMoreKey": "search-next",
    }


@pytest.fixture
def mock_profile_response():
    """Response from profile endpoint."""
    return {
        "user": {
            "id": "user-001",
            "username": "testuser",
            "screenName": "Test User",
        }
    }


@pytest.fixture
def mock_notifications_response():
    """Response from notifications list endpoint."""
    return {
        "data": [
            {"id": "notif-001", "type": "LIKE"}
        ]
    }


@pytest.fixture
def mock_unread_response():
    """Response from unread notifications endpoint."""
    return {"data": {"count": 3}}


@pytest.fixture
def mock_delete_response():
    """Response from delete endpoints."""
    return {"success": True}


@pytest.fixture
def mock_followers_response():
    """Response from followers list endpoint."""
    return {
        "data": [
            {"id": "user-002", "username": "follower1"}
        ],
        "loadMoreKey": "followers-next",
    }


@pytest.fixture
def mock_following_response():
    """Response from following list endpoint."""
    return {
        "data": [
            {"id": "user-003", "username": "following1"}
        ],
        "loadMoreKey": "following-next",
    }
