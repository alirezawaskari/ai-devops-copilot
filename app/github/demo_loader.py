"""Loads the bundled example repository as a `RepoSnapshot`.

This lets the API and demo scripts run a full, realistic analysis without a
GitHub token or network access -- useful for local evaluation, CI smoke
tests, and interviews/demos. The fixture lives in `app/examples/demo_repo/` and
intentionally contains representative Dockerfile, GitHub Actions, dependency,
and configuration problems for every analyzer to catch.
"""

from pathlib import Path

from app.github.repo_fetcher import categorize_path, is_path_safe
from app.github.schemas import RepoFile, RepoRef, RepoSnapshot

DEMO_REPO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_repo"
DEMO_REPO_REF = RepoRef(owner="ai-devops-copilot", name="demo-repo", ref="main")


def load_demo_snapshot(repo_root: Path = DEMO_REPO_PATH) -> RepoSnapshot:
    all_files = [p for p in repo_root.rglob("*") if p.is_file()]

    buckets: dict[str, list[RepoFile]] = {
        "dockerfile": [],
        "workflow": [],
        "dependency": [],
        "config": [],
        "source": [],
    }
    all_paths: list[str] = []

    for path in sorted(all_files):
        rel_path = path.relative_to(repo_root).as_posix()
        if not is_path_safe(rel_path):
            continue
        all_paths.append(rel_path)
        category = categorize_path(rel_path)
        if category:
            buckets[category].append(RepoFile(path=rel_path, content=path.read_text(encoding="utf-8")))

    return RepoSnapshot(
        repo=DEMO_REPO_REF,
        default_branch="main",
        all_paths=all_paths,
        dockerfiles=buckets["dockerfile"],
        workflows=buckets["workflow"],
        dependency_files=buckets["dependency"],
        config_files=buckets["config"],
        source_samples=buckets["source"],
        truncated=False,
    )
