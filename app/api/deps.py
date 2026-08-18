"""FastAPI dependency providers."""

from collections.abc import AsyncIterator

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import get_db_session
from app.workers.queue import get_arq_pool


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


async def get_queue() -> ArqRedis:
    return await get_arq_pool()
