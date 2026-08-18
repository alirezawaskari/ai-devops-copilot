from app.agents.schemas import Finding
from app.analyzers.dockerfile_analyzer import analyze_dockerfile
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class DockerfileTool(Tool):
    name = "analyze_dockerfiles"
    description = "Analyze Dockerfiles for security and optimization problems."

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return bool(snapshot.dockerfiles)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.dockerfiles:
            findings.extend(analyze_dockerfile(file))
        return findings
