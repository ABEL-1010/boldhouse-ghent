import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel import __version__
from sentinel.core.config import Settings, get_settings
from sentinel.core.logging import configure_logging
from sentinel.features import health

logger = logging.getLogger("sentinel")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    app = FastAPI(title="Sentinel", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)

    logger.info("Sentinel %s ready (CORS origins: %s)", __version__, settings.cors_origins)
    return app


app = create_app()
