"""Command-line interface for Sermon Illustrate."""

import argparse
import asyncio
import sys
from datetime import datetime

from src.storage.database import init_db, SessionLocal
from src.storage.models import Source, Article
from src.feeds.loader import init_data, load_sources_from_yaml
from src.feeds.fetcher import refresh_feeds, FeedFetcher, save_articles
from src.processors.analyzer import analyze_batch, ArticleAnalyzer, analyze_and_save


def cmd_init(args):
    """Initialize database and load default data."""
    print("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        result = init_data(db)
        print(f"  Sources added: {result['sources_added']}")
        print(f"  Sources skipped: {result['sources_skipped']}")
        print(f"  Themes added: {result['themes_added']}")
        print("Done!")
    finally:
        db.close()


def cmd_sources(args):
    """List all sources."""
    db = SessionLocal()
    try:
        sources = db.query(Source).order_by(Source.category, Source.name).all()

        if not sources:
            print("No sources found. Run 'init' first.")
            return

        print(f"\n{'Name':<30} {'Category':<12} {'Enabled':<8} {'Last Fetched':<20}")
        print("-" * 75)

        for source in sources:
            last_fetched = source.last_fetched.strftime("%Y-%m-%d %H:%M") if source.last_fetched else "Never"
            enabled = "Yes" if source.enabled else "No"
            print(f"{source.name:<30} {source.category:<12} {enabled:<8} {last_fetched:<20}")

        print(f"\nTotal: {len(sources)} sources")
    finally:
        db.close()


def cmd_fetch(args):
    """Fetch all enabled feeds."""
    print("Fetching feeds...")

    db = SessionLocal()
    try:
        result = asyncio.run(refresh_feeds(db))

        print(f"\nResults:")
        print(f"  Sources fetched: {result['sources_fetched']}")
        print(f"  Sources failed: {result['sources_failed']}")
        print(f"  New articles: {result['articles_new']}")
        print(f"  Updated articles: {result['articles_updated']}")

        if result["errors"]:
            print(f"\nErrors:")
            for err in result["errors"]:
                print(f"  - {err['source']}: {err['error']}")
    finally:
        db.close()


def cmd_fetch_one(args):
    """Fetch a single source by name."""
    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.name.ilike(f"%{args.name}%")).first()

        if not source:
            print(f"Source not found: {args.name}")
            return

        print(f"Fetching: {source.name} ({source.url})...")

        fetcher = FeedFetcher()
        articles, error = asyncio.run(fetcher.fetch_and_parse(source))

        if error:
            print(f"Error: {error}")
            return

        new_count, updated_count = save_articles(db, source, articles)
        print(f"Done! New: {new_count}, Updated: {updated_count}")

        if args.verbose:
            print(f"\nLatest articles:")
            for article in articles[:5]:
                print(f"  - {article.title[:60]}...")
    finally:
        db.close()


def cmd_articles(args):
    """List recent articles."""
    db = SessionLocal()
    try:
        query = db.query(Article).order_by(Article.published_at.desc())

        if args.category:
            query = query.join(Source).filter(Source.category == args.category)

        if args.bookmarked:
            query = query.filter(Article.bookmarked == True)

        articles = query.limit(args.limit).all()

        if not articles:
            print("No articles found.")
            return

        print(f"\n{'Title':<50} {'Source':<15} {'Score':<6} {'Published':<15}")
        print("-" * 90)

        for article in articles:
            title = article.title[:48] + ".." if len(article.title) > 50 else article.title
            source = article.source_name[:13] + ".." if len(article.source_name) > 15 else article.source_name
            score = str(int(article.illustration_score)) if article.illustration_score else "-"
            published = article._format_published()
            print(f"{title:<50} {source:<15} {score:<6} {published:<15}")

        print(f"\nShowing {len(articles)} articles")
    finally:
        db.close()


def cmd_stats(args):
    """Show database statistics."""
    db = SessionLocal()
    try:
        source_count = db.query(Source).count()
        enabled_sources = db.query(Source).filter(Source.enabled == True).count()
        article_count = db.query(Article).count()
        bookmarked_count = db.query(Article).filter(Article.bookmarked == True).count()
        analyzed_count = db.query(Article).filter(Article.illustration_score != None).count()

        # Articles by category
        from sqlalchemy import func

        category_counts = (
            db.query(Source.category, func.count(Article.id))
            .join(Article)
            .group_by(Source.category)
            .all()
        )

        # High potential articles
        high_potential = db.query(Article).filter(Article.illustration_score >= 85).count()

        print("\n=== Sermon Illustrate Stats ===\n")
        print(f"Sources: {source_count} ({enabled_sources} enabled)")
        print(f"Articles: {article_count}")
        print(f"  Analyzed: {analyzed_count}")
        print(f"  High potential (85+): {high_potential}")
        print(f"  Bookmarked: {bookmarked_count}")

        if category_counts:
            print(f"\nArticles by category:")
            for category, count in sorted(category_counts, key=lambda x: -x[1]):
                print(f"  {category}: {count}")
    finally:
        db.close()


def cmd_analyze(args):
    """Analyze articles for sermon illustration potential."""
    import os

    # Check for API key
    api_key = args.api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set.")
        print("Set it via environment variable or use --api-key flag.")
        return

    db = SessionLocal()
    try:
        print(f"Analyzing up to {args.limit} articles...")
        print()

        result = analyze_batch(db, limit=args.limit, api_key=api_key)

        print(f"Results:")
        print(f"  Analyzed: {result['analyzed']}")
        print(f"  Skipped (too short): {result['skipped']}")
        print(f"  Errors: {result['errors']}")
        print(f"  High potential (85+): {result['high_potential']}")

        if result["articles"] and args.verbose:
            print(f"\nAnalyzed articles:")
            for art in result["articles"]:
                themes = ", ".join(art["themes"][:3]) if art["themes"] else "none"
                print(f"  [{art['score']:3}] {art['title']}")
                print(f"        Themes: {themes}")

    finally:
        db.close()


def cmd_top(args):
    """Show top-scoring articles for sermon illustrations."""
    db = SessionLocal()
    try:
        query = (
            db.query(Article)
            .filter(Article.illustration_score != None)
            .order_by(Article.illustration_score.desc())
        )

        if args.category:
            query = query.join(Source).filter(Source.category == args.category)

        if args.min_score:
            query = query.filter(Article.illustration_score >= args.min_score)

        articles = query.limit(args.limit).all()

        if not articles:
            print("No analyzed articles found. Run 'analyze' first.")
            return

        print(f"\n{'Score':<6} {'Title':<55} {'Themes':<25}")
        print("-" * 90)

        for article in articles:
            title = article.title[:53] + ".." if len(article.title) > 55 else article.title
            themes = ", ".join([t.name for t in article.themes[:3]]) if article.themes else "-"
            if len(themes) > 23:
                themes = themes[:21] + ".."
            score = int(article.illustration_score)
            print(f"{score:<6} {title:<55} {themes:<25}")

        print(f"\nShowing {len(articles)} articles")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Sermon Illustrate CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize database and load sources")

    # sources
    sources_parser = subparsers.add_parser("sources", help="List all sources")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch all enabled feeds")

    # fetch-one
    fetch_one_parser = subparsers.add_parser("fetch-one", help="Fetch a single source")
    fetch_one_parser.add_argument("name", help="Source name (partial match)")
    fetch_one_parser.add_argument("-v", "--verbose", action="store_true", help="Show article titles")

    # articles
    articles_parser = subparsers.add_parser("articles", help="List recent articles")
    articles_parser.add_argument("-c", "--category", help="Filter by category")
    articles_parser.add_argument("-b", "--bookmarked", action="store_true", help="Only bookmarked")
    articles_parser.add_argument("-l", "--limit", type=int, default=20, help="Number of articles")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze articles with AI")
    analyze_parser.add_argument("-l", "--limit", type=int, default=10, help="Number of articles to analyze")
    analyze_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed results")
    analyze_parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")

    # top
    top_parser = subparsers.add_parser("top", help="Show top-scoring illustrations")
    top_parser.add_argument("-c", "--category", help="Filter by category")
    top_parser.add_argument("-m", "--min-score", type=int, default=0, help="Minimum score")
    top_parser.add_argument("-l", "--limit", type=int, default=20, help="Number of articles")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "sources":
        cmd_sources(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "fetch-one":
        cmd_fetch_one(args)
    elif args.command == "articles":
        cmd_articles(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "top":
        cmd_top(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
