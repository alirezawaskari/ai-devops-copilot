"""FastAPI application factory and entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routes import analysis, findings, fixes, health, repositories
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RateLimitMiddleware
from app.core.telemetry import configure_telemetry
from app.storage.database import create_all_tables, dispose_engine
from app.workers.queue import close_arq_pool

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("Starting ai-devops-copilot", extra={"app_env": settings.app_env})

    if settings.app_env == "local":
        await create_all_tables()

    yield

    await close_arq_pool()
    await dispose_engine()
    logger.info("Shutdown complete")


def create_app(redis_client: Redis | None = None) -> FastAPI:
    """Build the FastAPI application.

    `redis_client` is injectable so tests can pass an in-memory fake instead
    of connecting to a real Redis instance; production uses the module-level
    `app` below, which wires up a real client from `REDIS_URL`.
    """
    settings = get_settings()

    app = FastAPI(
        title="ai-devops-copilot",
        description="AI-powered DevOps assistant that analyzes GitHub repositories for "
        "Dockerfile, CI/CD, dependency, and configuration problems.",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    configure_telemetry(app)

    redis_client = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
    app.add_middleware(RateLimitMiddleware, redis_client=redis_client)

    app.include_router(health.router)
    app.include_router(analysis.router)
    app.include_router(findings.router)
    app.include_router(fixes.router)
    app.include_router(repositories.router)

    return app


app = create_app()
