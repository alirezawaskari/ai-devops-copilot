from app.agents.schemas import Finding
from app.analyzers.workflow_analyzer import analyze_workflow
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class WorkflowSecurityTool(Tool):
    name = "analyze_github_actions_security"
    description = "Analyze GitHub Actions workflow files for security misconfigurations."

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return bool(snapshot.workflows)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.workflows:
            findings.extend(analyze_workflow(file))
        return findings
