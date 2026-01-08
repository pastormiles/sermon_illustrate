"""Sermon-focused search for finding relevant illustrations."""

import os
import json
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from anthropic import Anthropic
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.storage.models import Article, Theme, Source


@dataclass
class SearchResult:
    """A search result with relevance info."""
    article_id: int
    title: str
    url: str
    source: str
    category: str
    summary: str
    illustration_score: int
    themes: list[str]
    relevance_score: int  # 0-100 relevance to query
    connection: str  # How this connects to the sermon topic
    published: str


QUERY_ANALYSIS_PROMPT = """Analyze this sermon search query and extract the key themes and concepts.

Query: {query}

Identify:
1. The core biblical/spiritual themes (e.g., trust, faith, redemption, forgiveness)
2. The emotional/human elements (e.g., fear, hope, struggle, transformation)
3. Key concepts that a news story might illustrate

Respond in JSON format:
{{
    "themes": ["theme1", "theme2", "theme3"],
    "concepts": ["concept1", "concept2", "concept3"],
    "sermon_angle": "Brief description of what kind of illustration would work"
}}

Only return JSON, no other text."""


RELEVANCE_RANKING_PROMPT = """You are helping a pastor find sermon illustrations.

Sermon Topic: {query}

Analyze these articles and rank them by how well they could illustrate the sermon topic.
For each relevant article, explain the connection to the sermon.

Articles:
{articles}

Return a JSON array of the top matches (most relevant first), maximum 10 results:
{{
    "results": [
        {{
            "article_id": <id>,
            "relevance_score": <0-100>,
            "connection": "<1-2 sentences explaining how this story illustrates the sermon topic>"
        }}
    ]
}}

Scoring guide:
- 90-100: Perfect illustration - directly demonstrates the biblical principle
- 70-89: Strong connection - clearly relates with minor adaptation
- 50-69: Moderate fit - usable with some creativity
- Below 50: Weak connection - skip these

Only include articles scoring 50+. Only return JSON, no other text."""


class SermonSearch:
    """Search for sermon illustrations using AI."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the search engine.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.anthropic_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

        if not self.anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.anthropic = Anthropic(api_key=self.anthropic_key)
        self.openai = OpenAI(api_key=self.openai_key) if self.openai_key else None

    def analyze_query(self, query: str) -> dict:
        """Analyze a sermon query to extract themes and concepts.

        Args:
            query: User's search query (verse, theme, idea)

        Returns:
            Dict with themes, concepts, and sermon_angle
        """
        prompt = QUERY_ANALYSIS_PROMPT.format(query=query)

        # Use GPT-4o-mini for fast query analysis (falls back to Haiku)
        if self.openai:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.choices[0].message.content.strip()
        else:
            response = self.anthropic.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        return json.loads(response_text)

    def rank_articles(self, query: str, articles: list[Article]) -> list[dict]:
        """Rank articles by relevance to sermon query.

        Args:
            query: User's search query
            articles: List of Article objects to rank

        Returns:
            List of ranking results with relevance scores and connections
        """
        # Format articles for the prompt (keep summaries short for speed)
        articles_text = "\n".join([
            f"[{a.id}] {a.title} | {(a.ai_summary or a.summary or '')[:150]} | Themes: {', '.join([t.name for t in a.themes])}"
            for a in articles
        ])

        prompt = RELEVANCE_RANKING_PROMPT.format(
            query=query,
            articles=articles_text,
        )

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        return result.get("results", [])


def search_illustrations(
    db: Session,
    query: str,
    limit: int = 20,
    min_illustration_score: int = 0,
    api_key: Optional[str] = None,
    category: Optional[str] = None,
) -> list[SearchResult]:
    """Search for sermon illustrations matching a query.

    Args:
        db: Database session
        query: Search query (verse, theme, idea)
        limit: Maximum results to return
        min_illustration_score: Minimum article illustration score
        api_key: Optional API key override
        category: Optional category filter (e.g., 'technology', 'economics')

    Returns:
        List of SearchResult objects ranked by relevance
    """
    search = SermonSearch(api_key=api_key)

    # Step 1: Analyze the query to get themes
    analysis = search.analyze_query(query)
    query_themes = [t.lower() for t in analysis.get("themes", [])]

    # Step 2: Find candidate articles
    # First, try to match by theme
    candidate_articles = []

    if query_themes:
        # Get articles that have matching themes
        theme_query = (
            db.query(Article)
            .join(Article.themes)
            .filter(Theme.name.in_(query_themes))
            .filter(Article.illustration_score >= min_illustration_score)
        )
        # Apply category filter if specified
        if category:
            theme_query = theme_query.join(Source).filter(Source.category == category)
        theme_matches = (
            theme_query
            .order_by(Article.illustration_score.desc().nullslast())
            .limit(50)
            .all()
        )
        candidate_articles.extend(theme_matches)

    # Also get top-scoring articles as fallback
    if len(candidate_articles) < 20:
        top_query = (
            db.query(Article)
            .filter(Article.illustration_score >= min_illustration_score)
            .filter(Article.illustration_score != None)
        )
        # Apply category filter if specified
        if category:
            top_query = top_query.join(Source).filter(Source.category == category)
        top_articles = (
            top_query
            .order_by(Article.illustration_score.desc())
            .limit(30)
            .all()
        )
        # Add articles not already in candidates
        existing_ids = {a.id for a in candidate_articles}
        for article in top_articles:
            if article.id not in existing_ids:
                candidate_articles.append(article)

    if not candidate_articles:
        return []

    # Step 3: Rank by relevance using AI (limit to 20 for speed)
    rankings = search.rank_articles(query, candidate_articles[:20])

    # Step 4: Build results
    results = []
    article_map = {a.id: a for a in candidate_articles}

    for rank in rankings[:limit]:
        article_id = rank.get("article_id")
        if article_id not in article_map:
            continue

        article = article_map[article_id]
        results.append(SearchResult(
            article_id=article.id,
            title=article.title,
            url=article.url,
            source=article.source_name or "Unknown",
            category=article.category or "general",
            summary=article.ai_summary or article.summary or "",
            illustration_score=int(article.illustration_score or 0),
            themes=[t.name for t in article.themes],
            relevance_score=rank.get("relevance_score", 0),
            connection=rank.get("connection", ""),
            published=article._format_published(),
        ))

    return results
