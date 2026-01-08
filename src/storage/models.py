"""Database models for Sermon Illustrate."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from src.storage.database import Base


# Association table for article themes
article_themes = Table(
    "article_themes",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id"), primary_key=True),
    Column("theme_id", Integer, ForeignKey("themes.id"), primary_key=True),
)


class Source(Base):
    """News source (RSS feed or API)."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False, unique=True)
    category = Column(String(50), nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    fetch_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles = relationship("Article", back_populates="source")

    def __repr__(self):
        return f"<Source {self.name}>"


class Article(Base):
    """News article from a feed."""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)

    # Article content
    title = Column(String(512), nullable=False)
    url = Column(String(1024), nullable=False, unique=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)

    # Metadata
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # AI analysis
    illustration_score = Column(Float, nullable=True, index=True)
    ai_summary = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)

    # User interaction
    bookmarked = Column(Boolean, default=False, index=True)
    notes = Column(Text, nullable=True)
    used_in_sermon = Column(Boolean, default=False)
    sermon_date = Column(DateTime, nullable=True)

    # Relationships
    source = relationship("Source", back_populates="articles")
    themes = relationship("Theme", secondary=article_themes, back_populates="articles")

    def __repr__(self):
        return f"<Article {self.title[:50]}>"

    @property
    def category(self):
        """Get category from source."""
        return self.source.category if self.source else None

    @property
    def source_name(self):
        """Get source name."""
        return self.source.name if self.source else None

    def to_dict(self):
        """Convert to dictionary for templates."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "summary": self.summary or self.ai_summary or "",
            "source": self.source_name,
            "category": self.category,
            "published": self._format_published(),
            "illustration_score": self.illustration_score or 0,
            "themes": [t.name for t in self.themes],
            "bookmarked": self.bookmarked,
            "notes": self.notes,
        }

    def _format_published(self):
        """Format published date as relative time."""
        if not self.published_at:
            return "Unknown"

        delta = datetime.utcnow() - self.published_at

        if delta.days > 7:
            return self.published_at.strftime("%b %d, %Y")
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} min ago"
        else:
            return "Just now"


class Theme(Base):
    """Biblical/sermon theme for categorization."""

    __tablename__ = "themes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    articles = relationship("Article", secondary=article_themes, back_populates="themes")

    def __repr__(self):
        return f"<Theme {self.name}>"


# Default themes to seed
DEFAULT_THEMES = [
    ("grace", "God's unmerited favor and forgiveness"),
    ("redemption", "Being saved or rescued from sin"),
    ("hope", "Expectation of good, trust in God's promises"),
    ("love", "Divine love, sacrificial love, compassion"),
    ("forgiveness", "Pardoning offenses, reconciliation"),
    ("faith", "Trust in God, belief without seeing"),
    ("justice", "Fairness, righteousness, moral rightness"),
    ("mercy", "Compassion, kindness to the suffering"),
    ("healing", "Physical, emotional, or spiritual restoration"),
    ("perseverance", "Endurance through trials, steadfastness"),
    ("community", "Fellowship, togetherness, the body of Christ"),
    ("service", "Serving others, humility, selflessness"),
    ("stewardship", "Responsible management of God's gifts"),
    ("wisdom", "Godly insight, discernment, understanding"),
    ("transformation", "Change, renewal, becoming new"),
    ("sacrifice", "Giving up something for a greater good"),
    ("restoration", "Returning to original state, renewal"),
    ("unity", "Oneness, harmony, working together"),
    ("purpose", "Divine calling, meaning, intentionality"),
    ("provision", "God's supply of needs, provision"),
]
