"""Shared Pydantic models for findings and recommendations.

These are the common currency between analyzers, tools, the agent, the API,
and the storage layer's ORM models.
"""

import enum

from pydantic import BaseModel, Field


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class Category(str, enum.Enum):
    DOCKERFILE = "dockerfile"
    GITHUB_ACTIONS = "github_actions"
    DEPENDENCY = "dependency"
    CICD = "cicd"
    CONFIGURATION = "configuration"
    RELIABILITY = "reliability"


class Finding(BaseModel):
    """A single, structured problem identified in a repository."""

    rule_id: str
    category: Category
    severity: Severity
    title: str
    description: str = Field(..., description="What was found, in concrete terms.")
    explanation: str = Field(..., description="Why this matters -- the risk or impact.")
    file_path: str | None = None
    line_number: int | None = None
    evidence: dict = Field(default_factory=dict)
    suggested_fix_summary: str | None = None

    def sort_key(self) -> tuple[int, str]:
        return (_SEVERITY_ORDER[self.severity], self.rule_id)


class FixProposal(BaseModel):
    """A suggested patch for a finding. Never applied automatically."""

    finding_rule_id: str
    summary: str
    patch_diff: str = Field(..., description="Unified diff illustrating the suggested change.")


class AnalysisReport(BaseModel):
    repo_full_name: str
    ref: str
    tools_used: list[str]
    findings: list[Finding]
    truncated: bool = False

    @property
    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts
