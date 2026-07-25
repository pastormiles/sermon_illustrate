# Sermon Illustrate - Development Progress

## Project Overview
A Python-based news feed scanning app for pastors to discover sermon illustrations across multiple disciplines (politics, economics, tech, psychology, medicine, science, culture). Delivers content via web dashboard and daily digest emails.

---

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy
- **Frontend**: HTMX + Jinja2 (MVP), upgradable to React/Vue
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **AI**: Claude API for content analysis
- **Scheduling**: APScheduler for feed fetching and digests

---

## Development Phases

### Phase 1: Project Setup
- [x] Initialize Git repository
- [x] Create project documentation (claude.md, README.md)
- [x] Set up project structure
- [x] Configure Python environment

### Phase 2: Feed Aggregation Engine
- [x] Implement RSS/Atom feed parser
- [x] Create news source configuration (sources.yaml)
- [x] Build async feed fetcher
- [x] Add rate limiting and error handling

### Phase 3: Database & Storage
- [x] Design database schema (articles, sources, tags, bookmarks)
- [x] Implement SQLAlchemy models
- [ ] Create migration system (Alembic)

### Phase 4: Content Processing
- [ ] Implement article text extraction
- [ ] Build category classifier
- [ ] Integrate Claude API for illustration detection
- [ ] Create biblical theme matcher

### Phase 5: Web Dashboard
- [x] Set up FastAPI application
- [x] Create base templates (HTMX + Jinja2)
- [x] Build article listing views
- [ ] Implement bookmark/save functionality
- [ ] Add search and filtering
- [ ] Create notes/annotation system

### Phase 6: Daily Digest
- [ ] Build digest content selector
- [ ] Create email templates
- [ ] Implement email delivery (SMTP/SendGrid)
- [ ] Add scheduling configuration

### Phase 7: Polish & Deploy
- [ ] Add user authentication
- [ ] Docker containerization
- [ ] GitHub Actions CI/CD
- [ ] Production deployment

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Web Framework | FastAPI | Async support, automatic OpenAPI docs, modern Python |
| Frontend | HTMX + Jinja2 | Simple, fast, minimal JS complexity for MVP |
| Database | SQLAlchemy + SQLite | Easy development, upgrade path to PostgreSQL |
| AI Provider | Claude API | Excellent reasoning for content analysis |

---

## Key Features

### Core
- Multi-source RSS/API feed aggregation
- Discipline categorization (politics, tech, medicine, etc.)
- AI-powered sermon illustration detection
- Biblical theme matching
- Web dashboard with bookmarks and notes
- Daily email digest

### Future
- Sermon topic search
- Scripture passage linking
- Full-text search archive
- Team collaboration
- Mobile app

---

## Session Log

### 2026-01-08
- Created project repository
- Initialized Git and connected to GitHub
- Set up project structure and documentation
- Created initial configuration files
- Built web dashboard with dark sidebar UI (FastAPI + Jinja2 + HTMX)
- Implemented feed aggregation engine (RSS parser, async fetcher)
- Created database models (Source, Article, Theme)
- Added CLI tool for feed management
- Successfully fetched 210 articles from 6 sources
- Connected live feed data to web dashboard

---

## Notes
- News sources to consider: AP News, Reuters, NPR, The Atlantic, Psychology Today, Nature, Science Daily, TechCrunch, The Economist
- Consider adding RSS feeds from Christian publications for context
- Look into NewsAPI.org for additional sources
