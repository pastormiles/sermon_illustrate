"""Web routes for the dashboard."""

import asyncio
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from src.storage.database import get_db, init_db
from src.storage.models import Source, Article
from src.feeds.fetcher import refresh_feeds
from src.feeds.loader import init_data
from src.processors.analyzer import analyze_batch
from src.processors.search import search_illustrations, SearchResult
from src.integrations.twitter import (
    get_twitter_config,
    TwitterAuth,
    get_client_from_token,
    search_tweets,
)

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "web" / "templates")

# Sample data for when database is empty
SAMPLE_ARTICLES = [
    {
        "id": 1,
        "title": "Scientists Discover New Treatment That Regenerates Heart Tissue",
        "source": "Nature News",
        "category": "medicine",
        "summary": "Researchers have developed a groundbreaking therapy that enables damaged heart tissue to regenerate, offering hope for millions with heart disease.",
        "url": "#",
        "published": "2 hours ago",
        "illustration_score": 92,
        "themes": ["healing", "hope", "restoration"],
        "bookmarked": False,
    },
    {
        "id": 2,
        "title": "Community Rallies to Rebuild After Devastating Flood",
        "source": "AP News",
        "category": "general",
        "summary": "Neighbors helping neighbors: A small town demonstrates the power of community as residents work together to rebuild homes destroyed by flooding.",
        "url": "#",
        "published": "4 hours ago",
        "illustration_score": 95,
        "themes": ["community", "perseverance", "love"],
        "bookmarked": False,
    },
    {
        "id": 3,
        "title": "Former Rivals Partner to Solve Global Water Crisis",
        "source": "The Economist",
        "category": "economics",
        "summary": "Two competing tech giants set aside differences to tackle clean water access in developing nations, proving cooperation trumps competition.",
        "url": "#",
        "published": "6 hours ago",
        "illustration_score": 88,
        "themes": ["reconciliation", "unity", "service"],
        "bookmarked": False,
    },
]

CATEGORIES = [
    {"id": "all", "name": "All Stories", "icon": "home", "color": "#6366f1"},
    {"id": "general", "name": "General", "icon": "newspaper", "color": "#8b5cf6"},
    {"id": "politics", "name": "Politics", "icon": "landmark", "color": "#ec4899"},
    {"id": "economics", "name": "Economics", "icon": "trending-up", "color": "#f59e0b"},
    {"id": "technology", "name": "Technology", "icon": "cpu", "color": "#10b981"},
    {"id": "science", "name": "Science", "icon": "flask-conical", "color": "#06b6d4"},
    {"id": "psychology", "name": "Psychology", "icon": "brain", "color": "#f97316"},
    {"id": "medicine", "name": "Medicine", "icon": "heart-pulse", "color": "#ef4444"},
    {"id": "culture", "name": "Culture", "icon": "palette", "color": "#a855f7"},
]

CATEGORY_COLORS = {cat["id"]: cat["color"] for cat in CATEGORIES}


def get_articles(db: Session, category: str = None, limit: int = 50) -> list[dict]:
    """Get articles from database, falling back to sample data."""
    query = db.query(Article).order_by(Article.published_at.desc().nullslast())

    if category and category != "all":
        query = query.join(Source).filter(Source.category == category)

    articles = query.limit(limit).all()

    if not articles:
        # Return sample data if database is empty
        if category and category != "all":
            return [a for a in SAMPLE_ARTICLES if a["category"] == category]
        return SAMPLE_ARTICLES

    return [article.to_dict() for article in articles]


def get_stats(db: Session) -> dict:
    """Get dashboard statistics."""
    article_count = db.query(Article).count()

    if article_count == 0:
        # Return sample stats
        return {
            "articles_today": len(SAMPLE_ARTICLES),
            "high_potential": 2,
            "bookmarked": 0,
            "sources": 12,
        }

    from datetime import datetime, timedelta
    from sqlalchemy import func

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "articles_today": db.query(Article).filter(Article.fetched_at >= today).count(),
        "high_potential": db.query(Article).filter(Article.illustration_score >= 85).count(),
        "bookmarked": db.query(Article).filter(Article.bookmarked == True).count(),
        "sources": db.query(Source).filter(Source.enabled == True).count(),
    }


@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page."""
    articles = get_articles(db)
    stats = get_stats(db)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "articles": articles,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": "all",
            "page_title": "Dashboard",
            "stats": stats,
        },
    )


@router.get("/category/{category_id}")
async def category_view(request: Request, category_id: str, db: Session = Depends(get_db)):
    """Category filtered view."""
    articles = get_articles(db, category=category_id)
    stats = get_stats(db)
    category_name = next((c["name"] for c in CATEGORIES if c["id"] == category_id), "All Stories")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "articles": articles,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": category_id,
            "page_title": category_name,
            "stats": stats,
        },
    )


@router.get("/bookmarks")
async def bookmarks(request: Request, db: Session = Depends(get_db)):
    """Bookmarked articles page."""
    articles = db.query(Article).filter(Article.bookmarked == True).order_by(Article.published_at.desc()).all()
    article_dicts = [a.to_dict() for a in articles]

    return templates.TemplateResponse(
        "bookmarks.html",
        {
            "request": request,
            "articles": article_dicts,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": None,
            "page_title": "Bookmarks",
        },
    )


@router.get("/digest")
async def digest(request: Request):
    """Daily digest settings page."""
    return templates.TemplateResponse(
        "digest.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": None,
            "page_title": "Daily Digest",
        },
    )


@router.get("/settings")
async def settings(request: Request, db: Session = Depends(get_db)):
    """Settings page."""
    # Get all sources sorted by category then name
    all_sources = db.query(Source).order_by(Source.category, Source.name).all()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": None,
            "page_title": "Settings",
            "all_sources": all_sources,
        },
    )


# API endpoints

@router.post("/api/refresh")
async def api_refresh_feeds(db: Session = Depends(get_db)):
    """Refresh all feeds."""
    result = await refresh_feeds(db)
    return result


@router.post("/api/init")
async def api_init_db(db: Session = Depends(get_db)):
    """Initialize database with sources and themes."""
    init_db()
    result = init_data(db)
    return result


@router.post("/api/bookmark/{article_id}")
async def api_toggle_bookmark(article_id: int, db: Session = Depends(get_db)):
    """Toggle bookmark status for an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.bookmarked = not article.bookmarked
    db.commit()

    return {"bookmarked": article.bookmarked}


@router.post("/api/analyze")
async def api_analyze_articles(db: Session = Depends(get_db), limit: int = 10):
    """Analyze unanalyzed articles with AI."""
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    result = analyze_batch(db, limit=limit, api_key=api_key)
    return result


# Search routes

@router.get("/search")
async def search_page(request: Request, q: str = "", category: str = "all", db: Session = Depends(get_db)):
    """Sermon search page."""
    results = []
    error = None

    if q:
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            error = "ANTHROPIC_API_KEY not configured"
        else:
            try:
                # Pass category filter to search
                cat_filter = None if category == "all" else category
                results = search_illustrations(db, q, limit=10, api_key=api_key, category=cat_filter)
                # Convert to dicts for template
                results = [
                    {
                        "id": r.article_id,
                        "title": r.title,
                        "url": r.url,
                        "source": r.source,
                        "category": r.category,
                        "summary": r.summary,
                        "illustration_score": r.illustration_score,
                        "themes": r.themes,
                        "relevance_score": r.relevance_score,
                        "connection": r.connection,
                        "published": r.published,
                    }
                    for r in results
                ]
            except Exception as e:
                error = str(e)

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q,
            "results": results,
            "error": error,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "selected_category": category,
            "active_category": None,
            "page_title": "Sermon Search",
        },
    )


@router.post("/api/search")
async def api_search(query: str, db: Session = Depends(get_db), limit: int = 10):
    """API endpoint for sermon search."""
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    results = search_illustrations(db, query, limit=limit, api_key=api_key)

    return {
        "query": query,
        "results": [
            {
                "article_id": r.article_id,
                "title": r.title,
                "url": r.url,
                "source": r.source,
                "category": r.category,
                "summary": r.summary,
                "illustration_score": r.illustration_score,
                "themes": r.themes,
                "relevance_score": r.relevance_score,
                "connection": r.connection,
                "published": r.published,
            }
            for r in results
        ],
    }


@router.post("/api/finish-illustration")
async def api_finish_illustration(request: Request, db: Session = Depends(get_db)):
    """Generate a sermon-ready illustration paragraph."""
    import os
    from openai import OpenAI
    from anthropic import Anthropic

    data = await request.json()
    article_id = data.get("article_id")
    title = data.get("title", "")
    connection = data.get("connection", "")
    sermon_topic = data.get("sermon_topic", "")

    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not openai_key and not anthropic_key:
        raise HTTPException(status_code=500, detail="No API key configured")

    # Get article details
    article = db.query(Article).filter(Article.id == article_id).first()
    summary = article.ai_summary or article.summary if article else ""

    prompt = f"""Write a sermon-ready illustration paragraph based on this news story.

Sermon Topic: {sermon_topic}
Story: {title}
Summary: {summary}
Connection: {connection}

Write a single paragraph (3-5 sentences) that a pastor could read directly in a sermon.
- Start with a compelling hook
- Tell the story briefly
- Connect it clearly to the spiritual point
- Keep it conversational and engaging
- Do NOT include phrases like "This story illustrates..." - just tell it naturally

Only return the paragraph, nothing else."""

    # Use GPT-4o-mini for speed (falls back to Haiku)
    if openai_key:
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        illustration = response.choices[0].message.content.strip()
    else:
        client = Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        illustration = response.content[0].text.strip()

    return {"illustration": illustration}


# Source management endpoints

@router.post("/api/sources/{source_id}/toggle")
async def api_toggle_source(source_id: int, request: Request, db: Session = Depends(get_db)):
    """Toggle a source's enabled status."""
    data = await request.json()
    enabled = data.get("enabled", True)

    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.enabled = enabled
    db.commit()

    return {"success": True, "enabled": source.enabled}


@router.delete("/api/sources/{source_id}")
async def api_delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a source and all its articles."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Delete all articles from this source
    db.query(Article).filter(Article.source_id == source_id).delete()
    db.delete(source)
    db.commit()

    return {"success": True}


@router.post("/api/sources")
async def api_add_source(request: Request, db: Session = Depends(get_db)):
    """Add a new feed source."""
    data = await request.json()
    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    category = data.get("category", "general")

    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")

    # Check if source already exists
    existing = db.query(Source).filter(Source.url == url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Source with this URL already exists")

    source = Source(name=name, url=url, category=category, enabled=True)
    db.add(source)
    db.commit()

    return {"success": True, "id": source.id}


# Twitter integration endpoints

@router.get("/auth/twitter")
async def twitter_auth_start():
    """Start Twitter OAuth flow."""
    config = get_twitter_config()
    if not config:
        raise HTTPException(status_code=500, detail="Twitter not configured. Add TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET to .env")

    auth_url, state = TwitterAuth.start_auth(config)
    return RedirectResponse(url=auth_url)


@router.get("/auth/twitter/callback")
async def twitter_auth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle Twitter OAuth callback."""
    if error:
        return RedirectResponse(url="/settings?twitter_error=" + error)

    if not code or not state:
        return RedirectResponse(url="/settings?twitter_error=missing_params")

    token = TwitterAuth.complete_auth(state, code)
    if not token:
        return RedirectResponse(url="/settings?twitter_error=auth_failed")

    # Store token (using "default" as user ID for single-user setup)
    TwitterAuth.store_token("default", token)

    return RedirectResponse(url="/settings?twitter_success=true")


@router.post("/api/twitter/disconnect")
async def twitter_disconnect():
    """Disconnect Twitter account."""
    TwitterAuth.remove_token("default")
    return {"success": True}


@router.get("/api/twitter/search")
async def twitter_search(q: str, limit: int = 20):
    """Search Twitter for tweets."""
    token = TwitterAuth.get_token("default")
    if not token:
        raise HTTPException(status_code=401, detail="Twitter not connected")

    client = get_client_from_token(token.get("access_token"))
    tweets = search_tweets(client, q, max_results=limit)

    return {"tweets": tweets}


@router.get("/api/twitter/status")
async def twitter_status():
    """Check if Twitter is connected."""
    config = get_twitter_config()
    token = TwitterAuth.get_token("default")

    return {
        "configured": config is not None,
        "connected": token is not None,
    }
