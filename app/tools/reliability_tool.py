from app.agents.schemas import Finding
from app.analyzers.reliability_analyzer import analyze_compose_reliability, analyze_source_reliability
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class ReliabilityTool(Tool):
    name = "analyze_reliability"
    description = (
        "Analyze source code and deployment config for obvious reliability problems "
        "(no timeouts, no healthchecks, swallowed errors)."
    )

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return bool(snapshot.source_samples) or bool(snapshot.config_files)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.source_samples:
            if file.path.endswith(".py"):
                findings.extend(analyze_source_reliability(file))
        for file in snapshot.config_files:
            basename = file.path.rsplit("/", 1)[-1].lower()
            if basename in ("docker-compose.yml", "docker-compose.yaml"):
                findings.extend(analyze_compose_reliability(file))
        return findings
