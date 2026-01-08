"""AI-powered article analyzer for sermon illustration potential."""

import os
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from anthropic import Anthropic
from sqlalchemy.orm import Session

from src.storage.models import Article, Theme


@dataclass
class AnalysisResult:
    """Result of AI analysis."""

    illustration_score: int  # 0-100
    summary: str  # AI-generated summary focused on sermon relevance
    themes: list[str]  # Matching biblical themes
    explanation: str  # Why this could be a good illustration


ANALYSIS_PROMPT = """You are an assistant helping pastors find sermon illustrations from news articles.

Analyze this article and evaluate its potential as a sermon illustration.

Article Title: {title}
Source: {source}
Category: {category}

Article Content:
{content}

---

Evaluate this article on these criteria:
1. **Human Interest**: Does it tell a compelling human story?
2. **Moral/Ethical Dimension**: Does it raise moral questions or demonstrate values?
3. **Universal Experience**: Does it connect to experiences most people can relate to?
4. **Redemption/Hope**: Does it show transformation, hope, or overcoming adversity?
5. **Sermon Applicability**: How easily can this connect to biblical themes?

Biblical themes to consider: grace, redemption, hope, love, forgiveness, faith, justice, mercy, healing, perseverance, community, service, stewardship, wisdom, transformation, sacrifice, restoration, unity, purpose, provision

Respond in this exact JSON format:
{{
    "illustration_score": <0-100 integer>,
    "summary": "<2-3 sentence summary focused on the sermon-relevant aspects>",
    "themes": ["<theme1>", "<theme2>", "<theme3>"],
    "explanation": "<1-2 sentences explaining why this would or wouldn't work as an illustration>"
}}

Scoring guide:
- 90-100: Exceptional illustration - powerful story with clear spiritual parallels
- 75-89: Good illustration - solid story that can connect to biblical themes
- 50-74: Moderate potential - useful with some creativity
- 25-49: Limited potential - mostly factual, hard to connect
- 0-24: Poor fit - technical, controversial, or inappropriate for sermons

Only return the JSON, no other text."""


class ArticleAnalyzer:
    """Analyzes articles for sermon illustration potential using Claude."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the analyzer.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)

    def analyze_article(self, article: Article) -> AnalysisResult:
        """Analyze a single article.

        Args:
            article: Article model instance

        Returns:
            AnalysisResult with score, summary, themes, explanation
        """
        # Use summary or content, prefer content if available
        content = article.content or article.summary or article.title

        # Truncate if too long (keep under ~2000 chars for efficiency)
        if len(content) > 2000:
            content = content[:2000] + "..."

        prompt = ANALYSIS_PROMPT.format(
            title=article.title,
            source=article.source_name or "Unknown",
            category=article.category or "general",
            content=content,
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON response
        response_text = response.content[0].text.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        return AnalysisResult(
            illustration_score=int(result.get("illustration_score", 50)),
            summary=result.get("summary", ""),
            themes=result.get("themes", []),
            explanation=result.get("explanation", ""),
        )


def analyze_and_save(db: Session, article: Article, analyzer: ArticleAnalyzer) -> bool:
    """Analyze an article and save results to database.

    Args:
        db: Database session
        article: Article to analyze
        analyzer: ArticleAnalyzer instance

    Returns:
        True if successful, False otherwise
    """
    try:
        result = analyzer.analyze_article(article)

        # Update article
        article.illustration_score = result.illustration_score
        article.ai_summary = result.summary
        article.analyzed_at = datetime.utcnow()

        # Link themes
        article.themes = []
        for theme_name in result.themes:
            theme = db.query(Theme).filter(Theme.name == theme_name.lower()).first()
            if theme:
                article.themes.append(theme)

        db.commit()
        return True

    except Exception as e:
        print(f"Error analyzing article {article.id}: {e}")
        return False


def analyze_batch(
    db: Session,
    limit: int = 10,
    min_content_length: int = 100,
    api_key: Optional[str] = None,
) -> dict:
    """Analyze a batch of unanalyzed articles.

    Args:
        db: Database session
        limit: Maximum articles to analyze
        min_content_length: Skip articles with less content
        api_key: Optional API key override

    Returns:
        Summary of analysis results
    """
    # Find unanalyzed articles with sufficient content
    articles = (
        db.query(Article)
        .filter(Article.analyzed_at == None)
        .filter(
            (Article.content != None) | (Article.summary != None)
        )
        .order_by(Article.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )

    if not articles:
        return {"analyzed": 0, "skipped": 0, "errors": 0, "message": "No articles to analyze"}

    analyzer = ArticleAnalyzer(api_key=api_key)

    results = {
        "analyzed": 0,
        "skipped": 0,
        "errors": 0,
        "high_potential": 0,  # Score >= 85
        "articles": [],
    }

    for article in articles:
        # Check content length
        content = article.content or article.summary or ""
        if len(content) < min_content_length:
            results["skipped"] += 1
            continue

        success = analyze_and_save(db, article, analyzer)

        if success:
            results["analyzed"] += 1
            if article.illustration_score and article.illustration_score >= 85:
                results["high_potential"] += 1
            results["articles"].append({
                "id": article.id,
                "title": article.title[:50] + "..." if len(article.title) > 50 else article.title,
                "score": article.illustration_score,
                "themes": [t.name for t in article.themes],
            })
        else:
            results["errors"] += 1

    return results
