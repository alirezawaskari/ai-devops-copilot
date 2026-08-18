"""GitHub Actions workflow security analysis."""

import re
from typing import Any

import yaml

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import find_line_number, make_finding
from app.github.schemas import RepoFile

_UNPINNED_USES_RE = re.compile(r"uses:\s*([^\s#]+)@([^\s#]+)")
_SECRET_ECHO_RE = re.compile(r"(echo|print)[^\n]*\$\{\{\s*secrets\.[A-Z0-9_]+\s*\}\}", re.IGNORECASE)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _safe_load(content: str) -> dict[Any, Any] | None:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def analyze_workflow(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    content = file.content
    data = _safe_load(content)

    if data is None:
        findings.append(
            make_finding(
                rule_id="GHA000",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.MEDIUM,
                title="Workflow file could not be parsed as YAML",
                description="The workflow file is not valid YAML, so it could not be fully analyzed.",
                explanation="A malformed workflow file will fail to run at all, silently disabling CI.",
                file_path=file.path,
                suggested_fix_summary="Validate the YAML syntax (e.g. with `yamllint` or the GitHub Actions editor).",
            )
        )
        return findings

    on_trigger = data.get("on") or data.get(True)  # PyYAML may parse bare `on:` as boolean True key
    trigger_names: set[str] = set()
    if isinstance(on_trigger, str):
        trigger_names = {on_trigger}
    elif isinstance(on_trigger, list):
        trigger_names = set(on_trigger)
    elif isinstance(on_trigger, dict):
        trigger_names = set(on_trigger.keys())

    jobs = data.get("jobs") or {}
    if not isinstance(jobs, dict):
        jobs = {}

    has_pr_target = "pull_request_target" in trigger_names
    checks_out_pr_head = "github.event.pull_request.head" in content

    if has_pr_target and checks_out_pr_head:
        findings.append(
            make_finding(
                rule_id="GHA001",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.CRITICAL,
                title="pull_request_target checks out untrusted PR head",
                description=(
                    "This workflow triggers on `pull_request_target` (which runs with "
                    "write-scoped secrets) and also checks out the PR head ref."
                ),
                explanation=(
                    "`pull_request_target` runs in the context of the base repository with "
                    "full secret access. Checking out and executing the fork's code in that "
                    "context lets any external contributor exfiltrate secrets or push to "
                    "protected branches via a malicious pull request."
                ),
                file_path=file.path,
                suggested_fix_summary=(
                    "Use `pull_request` instead, or if `pull_request_target` is required, never "
                    "check out or execute untrusted PR code within it."
                ),
            )
        )

    for match in _UNPINNED_USES_RE.finditer(content):
        action, ref = match.group(1), match.group(2)
        if action.startswith("./"):
            continue
        if not _SHA_RE.match(ref):
            line_no = find_line_number(content, match.group(0))
            findings.append(
                make_finding(
                    rule_id="GHA002",
                    category=Category.GITHUB_ACTIONS,
                    severity=Severity.MEDIUM,
                    title=f"Third-party action '{action}' is not pinned to a commit SHA",
                    description=f"`uses: {action}@{ref}` references a mutable tag/branch, not a commit SHA.",
                    explanation=(
                        "Tags like `@v4` can be moved by the action's maintainer (or an "
                        "attacker who compromises their account) to point at different code "
                        "without changing your workflow file. Pinning to a full commit SHA "
                        "makes the dependency immutable."
                    ),
                    file_path=file.path,
                    line_number=line_no,
                    evidence={"action": action, "ref": ref},
                    suggested_fix_summary=f"Pin `{action}` to a specific commit SHA, e.g. `{action}@<40-char-sha>`.",
                )
            )

    if _SECRET_ECHO_RE.search(content):
        line_no = None
        for lineno, line in enumerate(content.splitlines(), start=1):
            if _SECRET_ECHO_RE.search(line):
                line_no = lineno
                break
        findings.append(
            make_finding(
                rule_id="GHA003",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.HIGH,
                title="Secret value is echoed/printed in workflow logs",
                description="A workflow step prints a `secrets.*` value directly.",
                explanation=(
                    "GitHub masks exact-match secret strings in logs, but printing secrets "
                    "is fragile: string manipulation (base64, substrings, concatenation) "
                    "easily defeats masking and leaks the credential to anyone with log access."
                ),
                file_path=file.path,
                line_number=line_no,
                suggested_fix_summary="Never print secrets; pass them via env vars to the tool that needs them.",
            )
        )

    top_level_permissions = data.get("permissions")
    if top_level_permissions == "write-all" or (
        isinstance(top_level_permissions, dict)
        and any(v == "write" for v in top_level_permissions.values())
        and len(jobs) > 1
    ):
        findings.append(
            make_finding(
                rule_id="GHA004",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.MEDIUM,
                title="Overly broad workflow-level permissions",
                description="The workflow grants broad write permissions at the top level for all jobs.",
                explanation=(
                    "The default GITHUB_TOKEN should follow least privilege. Granting broad "
                    "write scopes to every job -- including ones that only need read access "
                    "-- expands the blast radius if any single job is compromised."
                ),
                file_path=file.path,
                suggested_fix_summary="Set `permissions: {}` at the workflow level and grant specific scopes per-job.",
            )
        )
    elif top_level_permissions is None:
        findings.append(
            make_finding(
                rule_id="GHA004B",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.LOW,
                title="No explicit `permissions` block",
                description="The workflow does not declare a `permissions` block.",
                explanation=(
                    "Without an explicit block, GITHUB_TOKEN defaults to the repository's "
                    "configured default, which on older repositories is broad read/write "
                    "access. Explicit permissions make the intended scope auditable."
                ),
                file_path=file.path,
                suggested_fix_summary="Add a `permissions:` block scoped to what each job actually needs.",
            )
        )

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        is_self_hosted = job.get("runs-on") == "self-hosted" or (
            isinstance(job.get("runs-on"), list) and "self-hosted" in job.get("runs-on", [])
        )
        if is_self_hosted and (has_pr_target or "pull_request" in trigger_names):
            findings.append(
                make_finding(
                    rule_id="GHA005",
                    category=Category.GITHUB_ACTIONS,
                    severity=Severity.HIGH,
                    title=f"Job '{job_name}' runs untrusted PR triggers on a self-hosted runner",
                    description=(
                        f"Job `{job_name}` uses a self-hosted runner and is triggered by pull request events."
                    ),
                    explanation=(
                        "Self-hosted runners execute on infrastructure you control. "
                        "Allowing external, untrusted pull requests to run on them lets an "
                        "attacker execute arbitrary code on your infrastructure."
                    ),
                    file_path=file.path,
                    suggested_fix_summary=(
                        "Use GitHub-hosted runners for PR-triggered jobs, or gate with required approval."
                    ),
                )
            )

    if re.search(r"(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)", content):
        findings.append(
            make_finding(
                rule_id="GHA006",
                category=Category.GITHUB_ACTIONS,
                severity=Severity.CRITICAL,
                title="Hardcoded credential detected in workflow file",
                description="The workflow file appears to contain a hardcoded credential or private key.",
                explanation=(
                    "Credentials committed to a workflow file are visible in the git history "
                    "forever, even after being removed in a later commit."
                ),
                file_path=file.path,
                suggested_fix_summary="Revoke the credential, remove it from history, and store it in GitHub Secrets.",
            )
        )

    return findings
