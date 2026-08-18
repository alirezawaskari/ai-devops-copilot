from app.agents.schemas import Finding
from app.analyzers.config_analyzer import analyze_docker_compose, analyze_env_example
from app.github.schemas import RepoSnapshot
from app.tools.base import Tool


class ConfigMistakesTool(Tool):
    name = "analyze_configuration"
    description = (
        "Analyze docker-compose and env files for exposed ports, hardcoded secrets, and missing restart policies."
    )

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return bool(snapshot.config_files)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.config_files:
            basename = file.path.rsplit("/", 1)[-1].lower()
            if basename in ("docker-compose.yml", "docker-compose.yaml"):
                findings.extend(analyze_docker_compose(file))
            elif basename == ".env.example":
                findings.extend(analyze_env_example(file))
        return findings
