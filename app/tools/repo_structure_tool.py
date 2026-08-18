"""Repository structure inspection tool.

Produces no findings on its own -- it exists so the tool registry (and the
LLM choosing among tools) has an explicit, inspectable way to look at "what's
in this repo" before deciding which specialized analyzers are worth running.
"""

from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class RepoStructureTool(Tool):
    name = "inspect_repo_structure"
    description = (
        "List the repository's file tree and categorized files (Dockerfiles, "
        "workflows, dependency manifests, config files) without analyzing them."
    )

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return True

    async def run(self, snapshot: RepoSnapshot) -> list:
        return []

    def summarize(self, snapshot: RepoSnapshot) -> dict:
        return {
            "total_files_seen": len(snapshot.all_paths),
            "dockerfiles": [f.path for f in snapshot.dockerfiles],
            "workflows": [f.path for f in snapshot.workflows],
            "dependency_files": [f.path for f in snapshot.dependency_files],
            "config_files": [f.path for f in snapshot.config_files],
            "truncated": snapshot.truncated,
        }
