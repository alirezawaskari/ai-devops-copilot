"""Thin async client over the GitHub REST API.

Only the endpoints this project needs are wrapped: repository metadata,
branch inspection, recursive tree listing, file content retrieval, and
(optionally) pull request creation. All mutating calls live in one place
(`create_pull_request_with_file`) and are never invoked automatically by the
analysis pipeline -- only by an explicit API call initiated by a human.
"""

import base64

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.errors import UpstreamServiceError
from app.core.logging import get_logger
from app.github.schemas import PullRequestResult, TreeEntry

logger = get_logger(__name__)


class GitHubClient:
    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        settings = get_settings()
        self._token = token if token is not None else settings.github_token
        self._base_url = base_url or settings.github_api_url

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type(httpx.TransportError),
    )
    async def _get(self, client: httpx.AsyncClient, path: str, **params: str) -> httpx.Response:
        response = await client.get(path, headers=self._headers(), params=params)
        if response.status_code >= 500:
            raise UpstreamServiceError(f"GitHub API error {response.status_code} for {path}")
        return response

    async def get_repository(self, owner: str, name: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15) as client:
            response = await self._get(client, f"/repos/{owner}/{name}")
            if response.status_code == 404:
                raise UpstreamServiceError(f"Repository {owner}/{name} not found", status_code=404)
            response.raise_for_status()
            return response.json()

    async def get_default_branch(self, owner: str, name: str) -> str:
        repo = await self.get_repository(owner, name)
        return str(repo.get("default_branch", "main"))

    async def list_tree(self, owner: str, name: str, ref: str) -> list[TreeEntry]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            response = await self._get(client, f"/repos/{owner}/{name}/git/trees/{ref}", recursive="1")
            response.raise_for_status()
            data = response.json()
            return [
                TreeEntry(path=item["path"], type=item["type"], size=item.get("size")) for item in data.get("tree", [])
            ]

    async def get_file_content(self, owner: str, name: str, path: str, ref: str) -> str:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15) as client:
            response = await self._get(client, f"/repos/{owner}/{name}/contents/{path}", ref=ref)
            response.raise_for_status()
            data = response.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return str(data.get("content", ""))

    async def create_pull_request_with_file(
        self,
        owner: str,
        name: str,
        *,
        base_branch: str,
        head_branch: str,
        file_path: str,
        file_content: str,
        commit_message: str,
        pr_title: str,
        pr_body: str,
    ) -> PullRequestResult:
        """Create a branch, commit a single file change, and open a PR.

        This is the ONLY code path in the project that mutates a GitHub
        repository. It is never called by the analysis or fix-proposal
        pipeline automatically -- only by the `/analyses/{id}/pull-request`
        endpoint, which requires an explicit, authenticated API call.
        """
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            base_ref = await self._get(client, f"/repos/{owner}/{name}/git/ref/heads/{base_branch}")
            base_ref.raise_for_status()
            base_sha = base_ref.json()["object"]["sha"]

            create_branch = await client.post(
                f"/repos/{owner}/{name}/git/refs",
                headers=self._headers(),
                json={"ref": f"refs/heads/{head_branch}", "sha": base_sha},
            )
            create_branch.raise_for_status()

            existing = await client.get(
                f"/repos/{owner}/{name}/contents/{file_path}",
                headers=self._headers(),
                params={"ref": head_branch},
            )
            body: dict[str, str] = {
                "message": commit_message,
                "content": base64.b64encode(file_content.encode("utf-8")).decode("ascii"),
                "branch": head_branch,
            }
            if existing.status_code == 200:
                body["sha"] = existing.json()["sha"]

            put_response = await client.put(
                f"/repos/{owner}/{name}/contents/{file_path}",
                headers=self._headers(),
                json=body,
            )
            put_response.raise_for_status()

            pr_response = await client.post(
                f"/repos/{owner}/{name}/pulls",
                headers=self._headers(),
                json={
                    "title": pr_title,
                    "body": pr_body,
                    "head": head_branch,
                    "base": base_branch,
                },
            )
            pr_response.raise_for_status()
            pr_data = pr_response.json()

            return PullRequestResult(
                number=pr_data["number"],
                url=pr_data["html_url"],
                head_branch=head_branch,
                base_branch=base_branch,
            )
