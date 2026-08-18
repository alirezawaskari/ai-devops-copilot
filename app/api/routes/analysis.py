from arq import ArqRedis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_queue
from app.api.schemas import AnalysisCreateRequest, AnalysisJobResponse
from app.core.errors import NotFoundError
from app.core.security import require_api_key
from app.storage.repositories.analysis_repo import AnalysisRepository
from app.storage.repositories.repository_repo import RepositoryRepository

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"], dependencies=[Depends(require_api_key)])


def _to_response(job, repository_full_name: str) -> AnalysisJobResponse:
    return AnalysisJobResponse(
        id=job.id,
        repository_full_name=repository_full_name,
        ref=job.ref,
        status=job.status,
        use_demo_fixture=job.use_demo_fixture,
        error_message=job.error_message,
        summary=job.summary,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("", response_model=AnalysisJobResponse, status_code=201)
async def start_analysis(
    payload: AnalysisCreateRequest,
    session: AsyncSession = Depends(get_db),
    queue: ArqRedis = Depends(get_queue),
) -> AnalysisJobResponse:
    owner = "ai-devops-copilot" if payload.use_demo_fixture else payload.owner
    name = "demo-repo" if payload.use_demo_fixture else payload.name

    repo_repo = RepositoryRepository(session)
    repository = await repo_repo.get_or_create(owner, name)

    analysis_repo = AnalysisRepository(session)
    job = await analysis_repo.create(repository.id, payload.ref, payload.use_demo_fixture)
    await session.commit()

    await queue.enqueue_job("run_analysis_job", job.id)

    return _to_response(job, repository.full_name)


@router.get("/{analysis_id}", response_model=AnalysisJobResponse)
async def get_analysis(analysis_id: str, session: AsyncSession = Depends(get_db)) -> AnalysisJobResponse:
    analysis_repo = AnalysisRepository(session)
    job = await analysis_repo.get(analysis_id)
    if job is None:
        raise NotFoundError(f"Analysis {analysis_id} not found.")

    repository = await RepositoryRepository(session).get(job.repository_id)
    repo_full_name = repository.full_name if repository else "unknown"

    return _to_response(job, repo_full_name)
