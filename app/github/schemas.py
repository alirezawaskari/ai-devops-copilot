"""Pydantic models for GitHub API data and repository snapshots."""

from pydantic import BaseModel, Field


class RepoRef(BaseModel):
    owner: str
    name: str
    ref: str = "main"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class TreeEntry(BaseModel):
    path: str
    type: str  # "blob" | "tree"
    size: int | None = None


class RepoFile(BaseModel):
    path: str
    content: str
    truncated: bool = False


class RepoSnapshot(BaseModel):
    """A safely-collected, size-bounded view of a repository used for analysis."""

    repo: RepoRef
    default_branch: str
    all_paths: list[str] = Field(default_factory=list)
    dockerfiles: list[RepoFile] = Field(default_factory=list)
    workflows: list[RepoFile] = Field(default_factory=list)
    dependency_files: list[RepoFile] = Field(default_factory=list)
    config_files: list[RepoFile] = Field(default_factory=list)
    source_samples: list[RepoFile] = Field(default_factory=list)
    truncated: bool = False


class PullRequestRequest(BaseModel):
    title: str
    body: str
    head_branch: str
    base_branch: str
    file_path: str
    file_content: str
    commit_message: str


class PullRequestResult(BaseModel):
    number: int
    url: str
    head_branch: str
    base_branch: str
