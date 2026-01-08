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
async def settings(request: Request):
    """Settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "category_colors": CATEGORY_COLORS,
            "active_category": None,
            "page_title": "Settings",
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
