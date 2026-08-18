"""GitHub repository actions.

`create_pull_request` is the ONLY endpoint in this project that mutates a
GitHub repository. It requires an authenticated, explicit API call with a
fully-specified file change -- the analysis pipeline never calls this on its
own, and there is no "auto-fix" mode.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import PullRequestCreateRequest, PullRequestResponse
from app.core.errors import NotFoundError, ValidationAppError
from app.core.security import require_api_key
from app.github.client import GitHubClient
from app.storage.repositories.repository_repo import RepositoryRepository

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"], dependencies=[Depends(require_api_key)])


@router.post("/{repository_id}/pull-request", response_model=PullRequestResponse, status_code=201)
async def create_pull_request(
    repository_id: str,
    payload: PullRequestCreateRequest,
    session: AsyncSession = Depends(get_db),
) -> PullRequestResponse:
    repository = await RepositoryRepository(session).get(repository_id)
    if repository is None:
        raise NotFoundError(f"Repository {repository_id} not found.")

    if repository.owner == "ai-devops-copilot" and repository.name == "demo-repo":
        raise ValidationAppError("Pull requests cannot be opened against the bundled demo repository.")

    client = GitHubClient()
    result = await client.create_pull_request_with_file(
        repository.owner,
        repository.name,
        base_branch=payload.base_branch,
        head_branch=payload.head_branch,
        file_path=payload.file_path,
        file_content=payload.file_content,
        commit_message=payload.commit_message,
        pr_title=payload.pr_title,
        pr_body=payload.pr_body,
    )

    return PullRequestResponse(
        number=result.number,
        url=result.url,
        head_branch=result.head_branch,
        base_branch=result.base_branch,
    )
