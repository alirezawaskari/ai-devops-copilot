from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.recommendation import RecommendationModel


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, finding_id: str, summary: str, patch_diff: str) -> RecommendationModel:
        rec = RecommendationModel(finding_id=finding_id, summary=summary, patch_diff=patch_diff)
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def list_for_finding(self, finding_id: str) -> list[RecommendationModel]:
        result = await self._session.execute(
            select(RecommendationModel).where(RecommendationModel.finding_id == finding_id)
        )
        return list(result.scalars().all())
