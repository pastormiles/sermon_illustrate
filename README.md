# Sermon Illustrate

A news feed scanning application for pastors to discover sermon illustrations across multiple disciplines.

## Features

- **Multi-Source Aggregation**: Scan RSS feeds and news APIs across politics, economics, tech, psychology, medicine, science, and culture
- **AI-Powered Analysis**: Uses Claude API to identify stories with sermon potential (moral dimensions, redemption themes, human interest)
- **Biblical Theme Matching**: Connect current events to biblical themes like grace, forgiveness, justice, and love
- **Web Dashboard**: Browse, save, annotate, and search illustrations
- **Daily Digest**: Receive email summaries of top illustrations

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: SQLAlchemy + SQLite/PostgreSQL
- **Frontend**: HTMX + Jinja2
- **AI**: Claude API (Anthropic)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- An Anthropic API key (for AI features)

### Installation

```bash
# Clone the repository
git clone https://github.com/pastormiles/sermon_illustrate.git
cd sermon_illustrate

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run the application
python -m src.main
```

## Project Structure

```
sermon_illustrate/
├── src/
│   ├── feeds/          # RSS/news source handlers
│   ├── processors/     # Content analysis & filtering
│   ├── storage/        # Database models
│   ├── api/            # FastAPI web backend
│   └── digest/         # Daily digest generator
├── config/
│   └── sources.yaml    # News source configuration
├── tests/
└── web/                # Frontend templates
```

## Development

See [claude.md](claude.md) for development progress and roadmap.

## License

MIT
