"""Fix proposal generation.

This endpoint only ever *suggests* a patch (a unified diff persisted as a
`Recommendation`). Nothing here writes to the analyzed repository -- applying
a change to GitHub requires a separate, explicit call to the pull-request
endpoint in `repositories.py`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import DevOpsAgent
from app.agents.schemas import Category, Finding, Severity
from app.api.deps import get_db
from app.api.schemas import FixProposalRequest, FixProposalResponse
from app.core.errors import NotFoundError
from app.core.security import require_api_key
from app.storage.repositories.finding_repo import FindingRepository
from app.storage.repositories.recommendation_repo import RecommendationRepository

router = APIRouter(prefix="/api/v1", tags=["fixes"], dependencies=[Depends(require_api_key)])


def _to_domain_finding(model) -> Finding:
    return Finding(
        rule_id=model.rule_id,
        category=Category(model.category),
        severity=Severity(model.severity),
        title=model.title,
        description=model.description,
        explanation=model.explanation,
        file_path=model.file_path,
        line_number=model.line_number,
        evidence=model.evidence or {},
    )


@router.post("/findings/{finding_id}/fix-proposals", response_model=FixProposalResponse, status_code=201)
async def create_fix_proposal(
    finding_id: str,
    payload: FixProposalRequest,
    session: AsyncSession = Depends(get_db),
) -> FixProposalResponse:
    finding_model = await FindingRepository(session).get(finding_id)
    if finding_model is None:
        raise NotFoundError(f"Finding {finding_id} not found.")

    agent = DevOpsAgent()
    finding = _to_domain_finding(finding_model)
    proposal = await agent.propose_fix(finding, payload.file_content)

    rec_repo = RecommendationRepository(session)
    recommendation = await rec_repo.create(finding_id, proposal.summary, proposal.patch_diff)
    await session.commit()

    return FixProposalResponse.model_validate(recommendation, from_attributes=True)


@router.get("/findings/{finding_id}/fix-proposals", response_model=list[FixProposalResponse])
async def list_fix_proposals(finding_id: str, session: AsyncSession = Depends(get_db)) -> list[FixProposalResponse]:
    finding_model = await FindingRepository(session).get(finding_id)
    if finding_model is None:
        raise NotFoundError(f"Finding {finding_id} not found.")

    recommendations = await RecommendationRepository(session).list_for_finding(finding_id)
    return [FixProposalResponse.model_validate(r, from_attributes=True) for r in recommendations]
