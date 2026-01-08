"""Async feed fetcher service."""

import asyncio
import httpx
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from src.feeds.parser import parse_feed, ParsedArticle
from src.storage.models import Source, Article


class FeedFetcher:
    """Async service for fetching RSS feeds."""

    def __init__(self, timeout: float = 30.0, max_concurrent: int = 5):
        """Initialize the fetcher.

        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent: Maximum concurrent feed fetches
        """
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.headers = {
            "User-Agent": "SermonIllustrate/1.0 (RSS Reader; +https://github.com/pastormiles/sermon_illustrate)"
        }

    async def fetch_feed(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch a single feed URL.

        Args:
            url: Feed URL to fetch

        Returns:
            Tuple of (content, error_message)
        """
        async with self.semaphore:
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=True
                ) as client:
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    return response.text, None
            except httpx.TimeoutException:
                return None, f"Timeout fetching {url}"
            except httpx.HTTPStatusError as e:
                return None, f"HTTP {e.response.status_code} from {url}"
            except Exception as e:
                return None, f"Error fetching {url}: {str(e)}"

    async def fetch_and_parse(self, source: Source) -> tuple[list[ParsedArticle], Optional[str]]:
        """Fetch and parse a feed source.

        Args:
            source: Source model instance

        Returns:
            Tuple of (articles, error_message)
        """
        content, error = await self.fetch_feed(source.url)

        if error:
            return [], error

        try:
            articles = parse_feed(content)
            return articles, None
        except Exception as e:
            return [], f"Error parsing feed: {str(e)}"

    async def fetch_all_sources(
        self, db: Session, enabled_only: bool = True
    ) -> dict[int, tuple[list[ParsedArticle], Optional[str]]]:
        """Fetch all sources from database.

        Args:
            db: Database session
            enabled_only: Only fetch enabled sources

        Returns:
            Dict mapping source_id to (articles, error)
        """
        query = db.query(Source)
        if enabled_only:
            query = query.filter(Source.enabled == True)

        sources = query.all()

        # Create tasks for all sources
        tasks = [self.fetch_and_parse(source) for source in sources]

        # Fetch all concurrently
        results = await asyncio.gather(*tasks)

        # Map results to source IDs
        return {source.id: result for source, result in zip(sources, results)}


def save_articles(
    db: Session,
    source: Source,
    parsed_articles: list[ParsedArticle],
    max_age_days: int = 30,
) -> tuple[int, int]:
    """Save parsed articles to database.

    Args:
        db: Database session
        source: Source the articles came from
        parsed_articles: List of parsed articles
        max_age_days: Skip articles older than this

    Returns:
        Tuple of (new_count, updated_count)
    """
    new_count = 0
    updated_count = 0
    cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0)

    for parsed in parsed_articles:
        # Skip very old articles
        if parsed.published_at:
            age = (datetime.utcnow() - parsed.published_at).days
            if age > max_age_days:
                continue

        # Check if article already exists
        existing = db.query(Article).filter(Article.url == parsed.url).first()

        if existing:
            # Update if we have new content
            if parsed.content and not existing.content:
                existing.content = parsed.content
                updated_count += 1
        else:
            # Create new article
            article = Article(
                source_id=source.id,
                title=parsed.title,
                url=parsed.url,
                summary=parsed.summary,
                content=parsed.content,
                author=parsed.author,
                published_at=parsed.published_at,
            )
            db.add(article)
            new_count += 1

    # Update source last_fetched
    source.last_fetched = datetime.utcnow()
    source.fetch_error = None

    db.commit()
    return new_count, updated_count


async def refresh_feeds(db: Session) -> dict:
    """Refresh all enabled feeds.

    Args:
        db: Database session

    Returns:
        Summary of fetch results
    """
    fetcher = FeedFetcher()
    results = await fetcher.fetch_all_sources(db)

    summary = {
        "sources_fetched": 0,
        "sources_failed": 0,
        "articles_new": 0,
        "articles_updated": 0,
        "errors": [],
    }

    for source_id, (articles, error) in results.items():
        source = db.query(Source).get(source_id)

        if error:
            source.fetch_error = error
            source.last_fetched = datetime.utcnow()
            db.commit()
            summary["sources_failed"] += 1
            summary["errors"].append({"source": source.name, "error": error})
        else:
            new_count, updated_count = save_articles(db, source, articles)
            summary["sources_fetched"] += 1
            summary["articles_new"] += new_count
            summary["articles_updated"] += updated_count

    return summary
