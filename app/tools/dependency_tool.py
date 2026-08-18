from app.agents.schemas import Finding
from app.analyzers.dependency_analyzer import analyze_dependency_file, check_lockfile_presence
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class DependencyRiskTool(Tool):
    name = "analyze_dependency_risk"
    description = "Analyze dependency manifests for unpinned, wildcard, or known-risky packages."

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return bool(snapshot.dependency_files)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.dependency_files:
            findings.extend(analyze_dependency_file(file))
        findings.extend(check_lockfile_presence(snapshot.dependency_files))
        return findings
