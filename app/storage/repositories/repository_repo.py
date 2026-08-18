from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.repository import RepositoryModel


class RepositoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, owner: str, name: str, default_branch: str = "main") -> RepositoryModel:
        full_name = f"{owner}/{name}"
        result = await self._session.execute(select(RepositoryModel).where(RepositoryModel.full_name == full_name))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        repo = RepositoryModel(owner=owner, name=name, full_name=full_name, default_branch=default_branch)
        self._session.add(repo)
        await self._session.flush()
        return repo

    async def get(self, repository_id: str) -> RepositoryModel | None:
        return await self._session.get(RepositoryModel, repository_id)
