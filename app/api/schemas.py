"""Request/response models for the public API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.schemas import Category, Severity


class AnalysisCreateRequest(BaseModel):
    owner: str = Field(..., description="GitHub repository owner/org. Ignored when use_demo_fixture=true.")
    name: str = Field(..., description="GitHub repository name. Ignored when use_demo_fixture=true.")
    ref: str = Field(default="main", description="Branch, tag, or commit SHA to analyze.")
    use_demo_fixture: bool = Field(
        default=False,
        description="Analyze the bundled example repository instead of calling GitHub.",
    )


class AnalysisJobResponse(BaseModel):
    id: str
    repository_full_name: str
    ref: str
    status: str
    use_demo_fixture: bool
    error_message: str | None = None
    summary: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class FindingResponse(BaseModel):
    id: str
    analysis_id: str
    category: Category
    severity: Severity
    rule_id: str
    title: str
    description: str
    explanation: str
    file_path: str | None = None
    line_number: int | None = None
    evidence: dict = Field(default_factory=dict)
    created_at: datetime


class FixProposalRequest(BaseModel):
    file_content: str | None = Field(
        default=None, description="Optional current file content to ground the suggested patch."
    )


class FixProposalResponse(BaseModel):
    id: str
    finding_id: str
    summary: str
    patch_diff: str
    generated_by: str
    created_at: datetime


class PullRequestCreateRequest(BaseModel):
    finding_id: str | None = Field(default=None, description="Finding this PR addresses, for context.")
    base_branch: str = "main"
    head_branch: str
    file_path: str
    file_content: str
    commit_message: str
    pr_title: str
    pr_body: str = ""


class PullRequestResponse(BaseModel):
    number: int
    url: str
    head_branch: str
    base_branch: str
