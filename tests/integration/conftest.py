"""Fixtures for API integration tests.

Builds a fully isolated FastAPI app per test: SQLite for storage, fakeredis
for rate limiting, and an inline "queue" that runs the analysis job
synchronously instead of going through a real arq worker process.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_queue
from app.main import create_app
from app.workers.tasks import run_analysis_job


class InlineQueue:
    """Stands in for the arq `ArqRedis` pool, running jobs immediately."""

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        if function == "run_analysis_job":
            await run_analysis_job({}, *args)


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    app = create_app(redis_client=FakeRedis())
    app.dependency_overrides[get_queue] = lambda: InlineQueue()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
