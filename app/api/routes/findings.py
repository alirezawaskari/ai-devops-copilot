from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import FindingResponse
from app.core.errors import NotFoundError
from app.core.security import require_api_key
from app.storage.repositories.analysis_repo import AnalysisRepository
from app.storage.repositories.finding_repo import FindingRepository

router = APIRouter(prefix="/api/v1", tags=["findings"], dependencies=[Depends(require_api_key)])


@router.get("/analyses/{analysis_id}/findings", response_model=list[FindingResponse])
async def list_findings(analysis_id: str, session: AsyncSession = Depends(get_db)) -> list[FindingResponse]:
    analysis_repo = AnalysisRepository(session)
    job = await analysis_repo.get(analysis_id)
    if job is None:
        raise NotFoundError(f"Analysis {analysis_id} not found.")

    findings = await FindingRepository(session).list_for_analysis(analysis_id)
    return [FindingResponse.model_validate(f, from_attributes=True) for f in findings]
