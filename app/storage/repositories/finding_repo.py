from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.finding import FindingModel


class FindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, findings: list[FindingModel]) -> list[FindingModel]:
        self._session.add_all(findings)
        await self._session.flush()
        return findings

    async def list_for_analysis(self, analysis_id: str) -> list[FindingModel]:
        result = await self._session.execute(
            select(FindingModel).where(FindingModel.analysis_id == analysis_id).order_by(FindingModel.severity)
        )
        return list(result.scalars().all())

    async def get(self, finding_id: str) -> FindingModel | None:
        return await self._session.get(FindingModel, finding_id)
