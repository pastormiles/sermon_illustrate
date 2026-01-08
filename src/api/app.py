"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Sermon Illustrate",
        description="News feed scanner for sermon illustrations",
        version="0.1.0",
    )

    # Mount static files
    static_path = Path(__file__).parent.parent.parent / "web" / "static"
    static_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    # Include routes
    app.include_router(router)

    return app
