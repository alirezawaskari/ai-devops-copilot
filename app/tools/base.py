"""Tool protocol and registry."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.agents.schemas import Finding
from app.github.schemas import RepoSnapshot


@dataclass(frozen=True)
class ToolSpec:
    """MCP-shaped tool description: name, description, JSON Schema input."""

    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        """Whether this tool has any relevant input to analyze."""

    @abstractmethod
    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        """Execute the analysis and return structured findings."""

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description)


class FunctionTool(Tool):
    """Adapts a plain sync/async function into a `Tool`."""

    def __init__(
        self,
        name: str,
        description: str,
        applies_to: Callable[[RepoSnapshot], bool],
        run_fn: Callable[[RepoSnapshot], Awaitable[list[Finding]]],
    ) -> None:
        self.name = name
        self.description = description
        self._applies_to = applies_to
        self._run_fn = run_fn

    def applies_to(self, snapshot: RepoSnapshot) -> bool:
        return self._applies_to(snapshot)

    async def run(self, snapshot: RepoSnapshot) -> list[Finding]:
        return await self._run_fn(snapshot)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def tool_specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def applicable_tools(self, snapshot: RepoSnapshot) -> list[Tool]:
        return [tool for tool in self._tools.values() if tool.applies_to(snapshot)]
