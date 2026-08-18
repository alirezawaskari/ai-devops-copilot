import httpx
import pytest
import respx

from app.core.errors import UpstreamServiceError
from app.github.client import GitHubClient


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="test-token", base_url="https://api.github.test")


@respx.mock
async def test_get_repository(client: GitHubClient):
    respx.get("https://api.github.test/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main", "name": "widgets"})
    )
    repo = await client.get_repository("acme", "widgets")
    assert repo["default_branch"] == "main"


@respx.mock
async def test_get_repository_not_found_raises(client: GitHubClient):
    respx.get("https://api.github.test/repos/acme/missing").mock(return_value=httpx.Response(404))
    with pytest.raises(UpstreamServiceError):
        await client.get_repository("acme", "missing")


@respx.mock
async def test_list_tree(client: GitHubClient):
    respx.get("https://api.github.test/repos/acme/widgets/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={"tree": [{"path": "Dockerfile", "type": "blob", "size": 120}]},
        )
    )
    entries = await client.list_tree("acme", "widgets", "main")
    assert entries[0].path == "Dockerfile"
    assert entries[0].type == "blob"


@respx.mock
async def test_get_file_content_decodes_base64(client: GitHubClient):
    import base64

    encoded = base64.b64encode(b"FROM python:3.12\n").decode()
    respx.get("https://api.github.test/repos/acme/widgets/contents/Dockerfile").mock(
        return_value=httpx.Response(200, json={"encoding": "base64", "content": encoded})
    )
    content = await client.get_file_content("acme", "widgets", "Dockerfile", "main")
    assert content == "FROM python:3.12\n"


@respx.mock
async def test_create_pull_request_with_file(client: GitHubClient):
    respx.get("https://api.github.test/repos/acme/widgets/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "base-sha"}})
    )
    respx.post("https://api.github.test/repos/acme/widgets/git/refs").mock(return_value=httpx.Response(201, json={}))
    respx.get("https://api.github.test/repos/acme/widgets/contents/Dockerfile").mock(return_value=httpx.Response(404))
    respx.put("https://api.github.test/repos/acme/widgets/contents/Dockerfile").mock(
        return_value=httpx.Response(201, json={})
    )
    respx.post("https://api.github.test/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(201, json={"number": 42, "html_url": "https://github.com/acme/widgets/pull/42"})
    )

    result = await client.create_pull_request_with_file(
        "acme",
        "widgets",
        base_branch="main",
        head_branch="fix/dockerfile-user",
        file_path="Dockerfile",
        file_content="FROM python:3.12-slim\nUSER appuser\n",
        commit_message="Pin base image and add non-root user",
        pr_title="Fix Dockerfile security issues",
        pr_body="Automated fix proposal review.",
    )

    assert result.number == 42
    assert result.url.endswith("/pull/42")
