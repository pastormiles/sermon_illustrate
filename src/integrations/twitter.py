"""Twitter/X integration for trending topics and search."""

import os
import tweepy
from typing import Optional
from dataclasses import dataclass


@dataclass
class TrendingTopic:
    """A trending topic from Twitter."""
    name: str
    tweet_volume: Optional[int]
    url: str


@dataclass
class TwitterConfig:
    """Twitter API configuration."""
    client_id: str
    client_secret: str
    callback_url: str


def get_twitter_config() -> Optional[TwitterConfig]:
    """Get Twitter configuration from environment."""
    client_id = os.getenv("TWITTER_CLIENT_ID")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")
    callback_url = os.getenv("TWITTER_CALLBACK_URL", "http://localhost:8000/auth/twitter/callback")

    if not client_id or not client_secret:
        return None

    return TwitterConfig(
        client_id=client_id,
        client_secret=client_secret,
        callback_url=callback_url
    )


def get_oauth2_handler(config: TwitterConfig) -> tweepy.OAuth2UserHandler:
    """Create OAuth2 handler for user authentication."""
    return tweepy.OAuth2UserHandler(
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=config.callback_url,
        scope=["tweet.read", "users.read", "offline.access"]
    )


def get_client_from_token(access_token: str) -> tweepy.Client:
    """Create a Twitter client from an access token."""
    return tweepy.Client(bearer_token=access_token)


def get_trending_topics(client: tweepy.Client, woeid: int = 23424977) -> list[TrendingTopic]:
    """
    Get trending topics for a location.

    Args:
        client: Authenticated Twitter client
        woeid: Where On Earth ID (default: 23424977 = United States)
               Other useful WOEIDs:
               - 1 = Worldwide
               - 23424977 = United States
               - 23424975 = United Kingdom

    Returns:
        List of trending topics
    """
    # Note: Twitter API v2 doesn't have a direct trends endpoint
    # We need to use v1.1 API for trends, which requires different auth
    # For now, we'll use the search functionality instead
    return []


def search_tweets(client: tweepy.Client, query: str, max_results: int = 10) -> list[dict]:
    """
    Search for recent tweets matching a query.

    Args:
        client: Authenticated Twitter client
        query: Search query
        max_results: Maximum number of results (10-100)

    Returns:
        List of tweet data
    """
    try:
        response = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "public_metrics", "author_id"],
            expansions=["author_id"],
            user_fields=["name", "username"]
        )

        if not response.data:
            return []

        # Build user lookup
        users = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users[user.id] = {"name": user.name, "username": user.username}

        tweets = []
        for tweet in response.data:
            author = users.get(tweet.author_id, {})
            tweets.append({
                "id": tweet.id,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "author_name": author.get("name", "Unknown"),
                "author_username": author.get("username", "unknown"),
                "metrics": tweet.public_metrics if hasattr(tweet, "public_metrics") else {},
            })

        return tweets
    except Exception as e:
        print(f"Twitter search error: {e}")
        return []


class TwitterAuth:
    """Manages Twitter OAuth2 authentication state."""

    # In-memory storage for OAuth state (in production, use database)
    _oauth_states: dict = {}
    _user_tokens: dict = {}  # user_id -> {access_token, refresh_token}

    @classmethod
    def start_auth(cls, config: TwitterConfig) -> tuple[str, str]:
        """
        Start OAuth flow.

        Returns:
            Tuple of (authorization_url, state)
        """
        handler = get_oauth2_handler(config)
        auth_url = handler.get_authorization_url()

        # Extract state from URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(auth_url)
        state = parse_qs(parsed.query).get("state", [""])[0]

        # Store handler for callback
        cls._oauth_states[state] = handler

        return auth_url, state

    @classmethod
    def complete_auth(cls, state: str, code: str) -> Optional[dict]:
        """
        Complete OAuth flow with callback code.

        Returns:
            Token dict with access_token, refresh_token, etc.
        """
        handler = cls._oauth_states.pop(state, None)
        if not handler:
            return None

        try:
            token = handler.fetch_token(code)
            return token
        except Exception as e:
            print(f"Twitter auth error: {e}")
            return None

    @classmethod
    def store_token(cls, user_id: str, token: dict):
        """Store user's Twitter token."""
        cls._user_tokens[user_id] = token

    @classmethod
    def get_token(cls, user_id: str) -> Optional[dict]:
        """Get user's Twitter token."""
        return cls._user_tokens.get(user_id)

    @classmethod
    def remove_token(cls, user_id: str):
        """Remove user's Twitter token."""
        cls._user_tokens.pop(user_id, None)
