from app.tools.base import ToolRegistry
from app.tools.cicd_tool import CicdMistakesTool
from app.tools.config_tool import ConfigMistakesTool
from app.tools.dependency_tool import DependencyRiskTool
from app.tools.dockerfile_tool import DockerfileTool
from app.tools.reliability_tool import ReliabilityTool
from app.tools.repo_structure_tool import RepoStructureTool
from app.tools.workflow_tool import WorkflowSecurityTool


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RepoStructureTool())
    registry.register(DockerfileTool())
    registry.register(WorkflowSecurityTool())
    registry.register(DependencyRiskTool())
    registry.register(CicdMistakesTool())
    registry.register(ConfigMistakesTool())
    registry.register(ReliabilityTool())
    return registry
