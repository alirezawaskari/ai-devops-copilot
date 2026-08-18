"""The DevOps analysis agent: tool selection, execution, and result synthesis.

Tool selection defaults to deterministic applicability checks (each tool
knows what kind of file it needs). This keeps the core analysis path fast,
free, and offline-testable. An optional LLM-assisted mode is available for
cases where a genuinely reasoning-driven selection is wanted -- see
`tool_selection_mode`.
"""

import json
from typing import Literal

from app.agents.prompts import TOOL_SELECTION_SYSTEM_PROMPT
from app.agents.schemas import AnalysisReport, Finding, FixProposal
from app.core.llm import LLMClient
from app.core.logging import get_logger
from app.github.schemas import RepoSnapshot
from app.tools.base import ToolRegistry
from app.tools.registry import build_default_registry

logger = get_logger(__name__)

ToolSelectionMode = Literal["heuristic", "llm"]


class DevOpsAgent:
    """Orchestrates repository analysis: selects tools, runs them, synthesizes findings."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        llm_client: LLMClient | None = None,
        tool_selection_mode: ToolSelectionMode = "heuristic",
    ) -> None:
        self._registry = registry or build_default_registry()
        self._llm = llm_client or LLMClient()
        self._tool_selection_mode = tool_selection_mode

    async def select_tools(self, snapshot: RepoSnapshot) -> list[str]:
        if self._tool_selection_mode == "heuristic" or not self._llm.usable:
            return [tool.name for tool in self._registry.applicable_tools(snapshot)]
        return await self._select_tools_via_llm(snapshot)

    async def _select_tools_via_llm(self, snapshot: RepoSnapshot) -> list[str]:
        from app.tools.repo_structure_tool import RepoStructureTool

        structure_tool = self._registry.get("inspect_repo_structure")
        summary = (
            structure_tool.summarize(snapshot)
            if isinstance(structure_tool, RepoStructureTool)
            else {}
        )
        specs = [
            {"name": s.name, "description": s.description}
            for s in self._registry.tool_specs()
            if s.name != "inspect_repo_structure"
        ]
        try:
            response = await self._llm.raw_client().chat.completions.create(
                model=self._llm.settings.llm_model,
                messages=[
                    {"role": "system", "content": TOOL_SELECTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps({"repo_summary": summary, "available_tools": specs}),
                    },
                ],
                temperature=0.0,
                max_tokens=200,
            )
            content = response.choices[0].message.content or "[]"
            names = json.loads(content)
            valid = {s.name for s in self._registry.tool_specs()}
            selected = [n for n in names if n in valid]
            return selected or [t.name for t in self._registry.applicable_tools(snapshot)]
        except Exception:
            logger.exception("LLM tool selection failed, falling back to heuristic selection")
            return [tool.name for tool in self._registry.applicable_tools(snapshot)]

    async def analyze(self, snapshot: RepoSnapshot) -> AnalysisReport:
        selected_names = await self.select_tools(snapshot)

        all_findings: list[Finding] = []
        tools_used: list[str] = []
        for name in selected_names:
            tool = self._registry.get(name)
            if tool is None:
                continue
            findings = await tool.run(snapshot)
            all_findings.extend(findings)
            tools_used.append(name)

        deduped = self._deduplicate(all_findings)
        deduped.sort(key=lambda f: f.sort_key())

        return AnalysisReport(
            repo_full_name=snapshot.repo.full_name,
            ref=snapshot.repo.ref,
            tools_used=tools_used,
            findings=deduped,
            truncated=snapshot.truncated,
        )

    @staticmethod
    def _deduplicate(findings: list[Finding]) -> list[Finding]:
        seen: set[tuple[str, str | None, int | None]] = set()
        deduped: list[Finding] = []
        for finding in findings:
            key = (finding.rule_id, finding.file_path, finding.line_number)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    async def summarize(self, report: AnalysisReport) -> str:
        return await self._llm.generate_summary(report)

    async def propose_fix(self, finding: Finding, file_content: str | None = None) -> FixProposal:
        """Generate a suggested patch for a finding. Never applies it automatically."""
        return await self._llm.generate_fix_proposal(finding, file_content)
