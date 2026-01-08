"""Sermon Illustrate - Main application entry point."""

import uvicorn
from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
