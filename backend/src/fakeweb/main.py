"""Fake web server for the demo: serves sandbox/web/ so fetch_url never touches the internet."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sentinel.core.config import get_settings


def create_app(web_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Sentinel fake web", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/", StaticFiles(directory=web_dir or get_settings().web_dir, html=True))
    return app


app = create_app()
