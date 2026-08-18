from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.analysis import AnalysisJobModel, AnalysisStatus


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, repository_id: str, ref: str, use_demo_fixture: bool = False) -> AnalysisJobModel:
        job = AnalysisJobModel(
            repository_id=repository_id,
            ref=ref,
            use_demo_fixture=use_demo_fixture,
            status=AnalysisStatus.PENDING.value,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, analysis_id: str) -> AnalysisJobModel | None:
        return await self._session.get(AnalysisJobModel, analysis_id)

    async def mark_running(self, job: AnalysisJobModel) -> None:
        job.status = AnalysisStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        await self._session.flush()

    async def mark_completed(self, job: AnalysisJobModel, summary: dict) -> None:
        job.status = AnalysisStatus.COMPLETED.value
        job.completed_at = datetime.now(UTC)
        job.summary = summary
        await self._session.flush()

    async def mark_failed(self, job: AnalysisJobModel, error_message: str) -> None:
        job.status = AnalysisStatus.FAILED.value
        job.completed_at = datetime.now(UTC)
        job.error_message = error_message[:2000]
        await self._session.flush()
