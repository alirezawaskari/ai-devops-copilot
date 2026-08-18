"""Shared pytest fixtures.

Tests run fully offline: SQLite backs the database, fakeredis backs both the
rate limiter and the background job queue. No Docker, network access, or
real API keys are required.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

os.environ.setdefault("API_KEYS", "test-key")
os.environ.setdefault("LLM_ENABLED", "false")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("GITHUB_TOKEN", "")

from app.config import get_settings  # noqa: E402
from app.storage.database import Base, dispose_engine, get_engine, get_session_factory  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    db_path = tmp_path / f"test-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session

    await dispose_engine()
