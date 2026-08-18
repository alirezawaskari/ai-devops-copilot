"""Safely collect a bounded, categorized snapshot of a repository's contents.

"Safe" here means:
  - hard caps on file count and total bytes fetched, so a huge monorepo
    cannot exhaust memory or blow the LLM context window
  - an extension/path allow-list, so we never fetch binaries, secrets-shaped
    files (`.pem`, `.key`, `id_rsa`, `.env`) or vendor/build directories
  - path traversal protection: every path returned by GitHub is validated to
    stay within the repository (no `..`, no absolute paths)
"""

import posixpath

from app.github.client import GitHubClient
from app.github.schemas import RepoFile, RepoRef, RepoSnapshot, TreeEntry

MAX_FILES_PER_CATEGORY = 15
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 3_000_000

EXCLUDED_DIR_PARTS = {
    "node_modules",
    "vendor",
    ".git",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".terraform",
}

SECRET_LIKE_NAMES = {".env", "id_rsa", "id_ed25519", ".npmrc", ".pypirc"}
SECRET_LIKE_SUFFIXES = (".pem", ".key", ".pfx", ".p12")

DEPENDENCY_FILENAMES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.mod",
    "go.sum",
    "gemfile",
    "gemfile.lock",
    "cargo.toml",
    "cargo.lock",
}

CONFIG_FILENAMES = {
    "docker-compose.yml",
    "docker-compose.yaml",
    "nginx.conf",
    "kubernetes.yaml",
    ".env.example",
    "terraform.tf",
}

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".go", ".rb", ".java"}


def is_path_safe(path: str) -> bool:
    if path.startswith("/") or ".." in path.split("/"):
        return False
    normalized = posixpath.normpath(path)
    if normalized.startswith("..") or normalized.startswith("/"):
        return False
    parts = set(path.split("/"))
    if parts & EXCLUDED_DIR_PARTS:
        return False
    basename = posixpath.basename(path).lower()
    return not (basename in SECRET_LIKE_NAMES or basename.endswith(SECRET_LIKE_SUFFIXES))


def categorize_path(path: str) -> str | None:
    basename = posixpath.basename(path).lower()
    lower_path = path.lower()

    if basename == "dockerfile" or basename.startswith("dockerfile."):
        return "dockerfile"
    if lower_path.startswith(".github/workflows/") and (basename.endswith(".yml") or basename.endswith(".yaml")):
        return "workflow"
    if basename in DEPENDENCY_FILENAMES:
        return "dependency"
    if basename in CONFIG_FILENAMES or basename.endswith(".ini") or basename == "config.yaml":
        return "config"
    if posixpath.splitext(basename)[1] in SOURCE_EXTENSIONS:
        return "source"
    return None


class SafeRepoFetcher:
    """Collects a `RepoSnapshot` from GitHub within strict safety bounds."""

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def fetch(self, repo_ref: RepoRef) -> RepoSnapshot:
        default_branch = await self._client.get_default_branch(repo_ref.owner, repo_ref.name)
        ref = repo_ref.ref or default_branch

        tree = await self._client.list_tree(repo_ref.owner, repo_ref.name, ref)
        safe_entries = [e for e in tree if e.type == "blob" and is_path_safe(e.path)]

        buckets: dict[str, list[TreeEntry]] = {
            "dockerfile": [],
            "workflow": [],
            "dependency": [],
            "config": [],
            "source": [],
        }
        for entry in safe_entries:
            category = categorize_path(entry.path)
            if category and len(buckets[category]) < MAX_FILES_PER_CATEGORY:
                buckets[category].append(entry)

        total_bytes = 0
        truncated = False

        async def fetch_bucket(entries: list[TreeEntry]) -> list[RepoFile]:
            nonlocal total_bytes, truncated
            results: list[RepoFile] = []
            for entry in entries:
                if entry.size and entry.size > MAX_FILE_BYTES:
                    truncated = True
                    continue
                if total_bytes >= MAX_TOTAL_BYTES:
                    truncated = True
                    break
                content = await self._client.get_file_content(repo_ref.owner, repo_ref.name, entry.path, ref)
                content_bytes = content.encode("utf-8")
                if len(content_bytes) > MAX_FILE_BYTES:
                    content = content_bytes[:MAX_FILE_BYTES].decode("utf-8", errors="ignore")
                    truncated = True
                total_bytes += len(content_bytes)
                results.append(RepoFile(path=entry.path, content=content))
            return results

        dockerfiles = await fetch_bucket(buckets["dockerfile"])
        workflows = await fetch_bucket(buckets["workflow"])
        dependency_files = await fetch_bucket(buckets["dependency"])
        config_files = await fetch_bucket(buckets["config"])
        source_samples = await fetch_bucket(buckets["source"][:5])

        return RepoSnapshot(
            repo=repo_ref,
            default_branch=default_branch,
            all_paths=[e.path for e in safe_entries][:2000],
            dockerfiles=dockerfiles,
            workflows=workflows,
            dependency_files=dependency_files,
            config_files=config_files,
            source_samples=source_samples,
            truncated=truncated,
        )
