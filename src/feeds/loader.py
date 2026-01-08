"""Load feed sources from configuration."""

import yaml
from pathlib import Path
from sqlalchemy.orm import Session

from src.storage.models import Source, Theme, DEFAULT_THEMES


def load_sources_from_yaml(db: Session, config_path: Path = None) -> tuple[int, int]:
    """Load sources from YAML config file.

    Args:
        db: Database session
        config_path: Path to sources.yaml (defaults to config/sources.yaml)

    Returns:
        Tuple of (added_count, skipped_count)
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "sources.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    added = 0
    skipped = 0

    for source_config in config.get("sources", []):
        url = source_config.get("url")
        if not url:
            continue

        # Check if source already exists
        existing = db.query(Source).filter(Source.url == url).first()
        if existing:
            skipped += 1
            continue

        # Create new source
        source = Source(
            name=source_config.get("name", "Unknown"),
            url=url,
            category=source_config.get("category", "general"),
            enabled=source_config.get("enabled", True),
        )
        db.add(source)
        added += 1

    db.commit()
    return added, skipped


def seed_themes(db: Session) -> int:
    """Seed default biblical themes.

    Args:
        db: Database session

    Returns:
        Number of themes added
    """
    added = 0

    for name, description in DEFAULT_THEMES:
        existing = db.query(Theme).filter(Theme.name == name).first()
        if not existing:
            theme = Theme(name=name, description=description)
            db.add(theme)
            added += 1

    db.commit()
    return added


def init_data(db: Session) -> dict:
    """Initialize database with sources and themes.

    Args:
        db: Database session

    Returns:
        Summary of initialization
    """
    sources_added, sources_skipped = load_sources_from_yaml(db)
    themes_added = seed_themes(db)

    return {
        "sources_added": sources_added,
        "sources_skipped": sources_skipped,
        "themes_added": themes_added,
    }
