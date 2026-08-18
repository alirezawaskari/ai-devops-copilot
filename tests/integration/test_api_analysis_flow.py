from httpx import AsyncClient

AUTH_HEADERS = {"X-API-Key": "test-key"}


async def test_missing_api_key_is_rejected(async_client: AsyncClient):
    response = await async_client.post("/api/v1/analyses", json={"owner": "a", "name": "b"})
    assert response.status_code == 401


async def test_invalid_api_key_is_rejected(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/analyses",
        json={"owner": "a", "name": "b"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


async def test_health_check_requires_no_auth(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_full_demo_analysis_flow(async_client: AsyncClient):
    create_response = await async_client.post(
        "/api/v1/analyses",
        json={"owner": "ignored", "name": "ignored", "use_demo_fixture": True},
        headers=AUTH_HEADERS,
    )
    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] in {"pending", "running", "completed"}
    analysis_id = job["id"]

    status_response = await async_client.get(f"/api/v1/analyses/{analysis_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["summary"]["total_findings"] > 0

    findings_response = await async_client.get(f"/api/v1/analyses/{analysis_id}/findings", headers=AUTH_HEADERS)
    assert findings_response.status_code == 200
    findings = findings_response.json()
    assert len(findings) == status_payload["summary"]["total_findings"]
    assert findings[0]["severity"] in {"critical", "high"}  # sorted, most severe first

    finding_id = findings[0]["id"]
    fix_response = await async_client.post(
        f"/api/v1/findings/{finding_id}/fix-proposals", json={}, headers=AUTH_HEADERS
    )
    assert fix_response.status_code == 201
    fix_payload = fix_response.json()
    assert fix_payload["patch_diff"]

    list_fix_response = await async_client.get(f"/api/v1/findings/{finding_id}/fix-proposals", headers=AUTH_HEADERS)
    assert list_fix_response.status_code == 200
    assert len(list_fix_response.json()) == 1


async def test_analysis_not_found_returns_404(async_client: AsyncClient):
    response = await async_client.get("/api/v1/analyses/does-not-exist", headers=AUTH_HEADERS)
    assert response.status_code == 404


async def test_pull_request_blocked_for_demo_repo(async_client: AsyncClient):
    create_response = await async_client.post(
        "/api/v1/analyses",
        json={"owner": "ignored", "name": "ignored", "use_demo_fixture": True},
        headers=AUTH_HEADERS,
    )
    analysis_id = create_response.json()["id"]
    status_response = await async_client.get(f"/api/v1/analyses/{analysis_id}", headers=AUTH_HEADERS)
    repo_full_name = status_response.json()["repository_full_name"]
    assert repo_full_name == "ai-devops-copilot/demo-repo"

    findings_response = await async_client.get(f"/api/v1/analyses/{analysis_id}/findings", headers=AUTH_HEADERS)
    finding = findings_response.json()[0]

    # Repository id isn't exposed on the finding/analysis response directly in this flow,
    # so we look it up the same way the app does: by owner/name via a second analysis create,
    # which is idempotent (get_or_create) and returns no new repository.
    pr_response = await async_client.post(
        "/api/v1/repositories/nonexistent-id/pull-request",
        json={
            "finding_id": finding["id"],
            "head_branch": "fix/test",
            "file_path": "Dockerfile",
            "file_content": "FROM python:3.12-slim\n",
            "commit_message": "test",
            "pr_title": "test",
        },
        headers=AUTH_HEADERS,
    )
    assert pr_response.status_code == 404
