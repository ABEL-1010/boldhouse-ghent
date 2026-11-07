import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel import __version__
from sentinel.core.config import Settings, get_settings
from sentinel.core.logging import configure_logging
from sentinel.features import detection, events, gateway, health
from sentinel.features.tools import ToolService, ensure_sandbox

logger = logging.getLogger("sentinel")


def _default_scorer(settings: Settings) -> detection.SentinelScorer:
    model = (
        detection.DetectionModel.load(settings.model_path)
        if settings.model_path.is_file()
        else None
    )
    return detection.SentinelScorer(detection.load_honeytokens(settings.honeytokens_path), model)


def create_app(
    settings: Settings | None = None,
    *,
    scorer: detection.Scorer | None = None,
    tools: ToolService | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    bus = events.EventBus()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if tools is None and ensure_sandbox(
            settings.seed_workspace, settings.runtime_workspace, settings.outbox_path
        ):
            logger.info("Created runtime sandbox at %s", settings.runtime_workspace)
        yield
        bus.close()

    app = FastAPI(title="Sentinel", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    tool_service = tools or ToolService.from_settings(settings)
    allowed_domains = frozenset(d.lower() for d in settings.sentinel_allowed_domains)
    app.state.event_bus = bus
    app.state.gateway = gateway.GatewayService(
        tools=tool_service,
        scorer=scorer or _default_scorer(settings),
        bus=bus,
        decision_timeout_seconds=settings.decision_timeout_seconds,
        new_context=lambda: detection.SessionContext(tool_service.workspace, allowed_domains),
    )
    app.include_router(health.router)
    app.include_router(gateway.router)
    app.include_router(events.router)

    logger.info("Sentinel %s ready (CORS origins: %s)", __version__, settings.cors_origins)
    return app


app = create_app()
