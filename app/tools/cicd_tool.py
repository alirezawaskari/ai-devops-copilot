from app.agents.schemas import Finding
from app.analyzers.cicd_analyzer import analyze_cicd_setup
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class CicdMistakesTool(Tool):
    name = "analyze_cicd_mistakes"
    description = (
        "Analyze CI/CD process for common mistakes: missing CI, ignored failures, no caching, unguarded deploys."
    )

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return True

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        return analyze_cicd_setup(snapshot.workflows)
