"""RSS/Atom feed parser."""

import feedparser
from datetime import datetime
from time import mktime
from typing import Optional
from dataclasses import dataclass


@dataclass
class ParsedArticle:
    """Parsed article from a feed."""

    title: str
    url: str
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None

    def __post_init__(self):
        # Clean up summary - remove HTML tags for plain text
        if self.summary:
            self.summary = self._strip_html(self.summary)
        if self.content:
            self.content = self._strip_html(self.content)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from text."""
        import re

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        clean = clean.replace("&nbsp;", " ")
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&#39;", "'")
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean


def parse_feed(feed_content: str) -> list[ParsedArticle]:
    """Parse RSS/Atom feed content into articles.

    Args:
        feed_content: Raw XML content of the feed

    Returns:
        List of ParsedArticle objects
    """
    parsed = feedparser.parse(feed_content)
    articles = []

    for entry in parsed.entries:
        # Get the article URL
        url = entry.get("link", "")
        if not url:
            continue

        # Get title
        title = entry.get("title", "Untitled")

        # Get summary/description
        summary = None
        if "summary" in entry:
            summary = entry.summary
        elif "description" in entry:
            summary = entry.description

        # Get full content if available
        content = None
        if "content" in entry and entry.content:
            content = entry.content[0].get("value", "")

        # Get author
        author = entry.get("author", None)

        # Get published date
        published_at = None
        if "published_parsed" in entry and entry.published_parsed:
            try:
                published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
            except (ValueError, OverflowError):
                pass
        elif "updated_parsed" in entry and entry.updated_parsed:
            try:
                published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))
            except (ValueError, OverflowError):
                pass

        articles.append(
            ParsedArticle(
                title=title,
                url=url,
                summary=summary,
                content=content,
                author=author,
                published_at=published_at,
            )
        )

    return articles


def get_feed_info(feed_content: str) -> dict:
    """Get metadata about a feed.

    Args:
        feed_content: Raw XML content of the feed

    Returns:
        Dictionary with feed metadata
    """
    parsed = feedparser.parse(feed_content)
    feed = parsed.feed

    return {
        "title": feed.get("title", "Unknown"),
        "description": feed.get("description", ""),
        "link": feed.get("link", ""),
        "language": feed.get("language", ""),
        "updated": feed.get("updated", ""),
        "entry_count": len(parsed.entries),
    }
