"""Background job that runs a full repository analysis.

Invoked via arq (`arq app.workers.tasks.WorkerSettings`), triggered by the
`POST /api/v1/analyses` endpoint enqueuing `run_analysis_job`.
"""

from typing import Any

from app.agents.orchestrator import DevOpsAgent
from app.core.logging import get_logger
from app.github.client import GitHubClient
from app.github.demo_loader import load_demo_snapshot
from app.github.repo_fetcher import SafeRepoFetcher
from app.github.schemas import RepoRef, RepoSnapshot
from app.storage.database import session_scope
from app.storage.models.finding import FindingModel
from app.storage.repositories.analysis_repo import AnalysisRepository
from app.storage.repositories.finding_repo import FindingRepository
from app.workers.queue import redis_settings

logger = get_logger(__name__)


async def _build_snapshot(repo_full_name: str, ref: str, use_demo_fixture: bool) -> RepoSnapshot:
    if use_demo_fixture:
        return load_demo_snapshot()

    owner, _, name = repo_full_name.partition("/")
    client = GitHubClient()
    fetcher = SafeRepoFetcher(client)
    return await fetcher.fetch(RepoRef(owner=owner, name=name, ref=ref))


async def run_analysis_job(ctx: dict[str, Any], analysis_id: str) -> None:
    async with session_scope() as session:
        analysis_repo = AnalysisRepository(session)

        job = await analysis_repo.get(analysis_id)
        if job is None:
            logger.error("Analysis job not found", extra={"analysis_id": analysis_id})
            return

        from app.storage.repositories.repository_repo import RepositoryRepository

        repository = await RepositoryRepository(session).get(job.repository_id)
        if repository is None:
            await analysis_repo.mark_failed(job, "Repository record not found.")
            return

        await analysis_repo.mark_running(job)

    try:
        snapshot = await _build_snapshot(repository.full_name, job.ref, job.use_demo_fixture)
        agent = DevOpsAgent()
        report = await agent.analyze(snapshot)
        narrative = await agent.summarize(report)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analysis failed", extra={"analysis_id": analysis_id})
        async with session_scope() as session:
            job = await AnalysisRepository(session).get(analysis_id)
            if job is not None:
                await AnalysisRepository(session).mark_failed(job, str(exc))
        return

    async with session_scope() as session:
        analysis_repo = AnalysisRepository(session)
        finding_repo = FindingRepository(session)
        job = await analysis_repo.get(analysis_id)
        if job is None:
            return

        finding_models = [
            FindingModel(
                analysis_id=analysis_id,
                category=f.category.value,
                severity=f.severity.value,
                rule_id=f.rule_id,
                title=f.title,
                description=f.description,
                explanation=f.explanation,
                file_path=f.file_path,
                line_number=f.line_number,
                evidence=f.evidence,
            )
            for f in report.findings
        ]
        await finding_repo.bulk_create(finding_models)

        summary = {
            "tools_used": report.tools_used,
            "counts_by_severity": report.counts_by_severity,
            "total_findings": len(report.findings),
            "truncated": report.truncated,
            "narrative": narrative,
        }
        await analysis_repo.mark_completed(job, summary)

    logger.info(
        "Analysis completed",
        extra={"analysis_id": analysis_id, "findings": len(report.findings)},
    )


class WorkerSettings:
    functions = [run_analysis_job]
    redis_settings = redis_settings()
