"""Common CI/CD process mistakes, distinct from workflow-file security issues."""

import yaml

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import make_finding
from app.github.schemas import RepoFile


def analyze_cicd_setup(workflows: list[RepoFile]) -> list[Finding]:
    findings: list[Finding] = []

    if not workflows:
        findings.append(
            make_finding(
                rule_id="CICD001",
                category=Category.CICD,
                severity=Severity.HIGH,
                title="No GitHub Actions workflow found",
                description="The repository has no `.github/workflows/*.yml` files.",
                explanation=(
                    "Without CI, regressions and broken builds are only discovered after "
                    "merge (or in production), instead of being caught automatically on "
                    "every pull request."
                ),
                suggested_fix_summary=(
                    "Add a workflow that installs dependencies, lints, type-checks, and runs tests on every PR."
                ),
            )
        )
        return findings

    for file in workflows:
        try:
            data = yaml.safe_load(file.content)
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue

        jobs = data.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps") or []
            if not isinstance(steps, list):
                continue

            has_dependency_install = any(
                isinstance(s, dict)
                and ("run" in s)
                and any(kw in str(s.get("run", "")) for kw in ("pip install", "npm install", "npm ci"))
                for s in steps
            )
            has_cache = "actions/cache" in file.content or "cache:" in file.content
            if has_dependency_install and not has_cache:
                findings.append(
                    make_finding(
                        rule_id="CICD003",
                        category=Category.CICD,
                        severity=Severity.LOW,
                        title=f"Job '{job_name}' installs dependencies without caching",
                        description="Dependencies are installed fresh on every run with no cache step.",
                        explanation=(
                            "Uncached dependency installation slows every CI run and adds "
                            "unnecessary load on package registries. This is a cost/speed "
                            "issue, not a correctness one."
                        ),
                        file_path=file.path,
                        suggested_fix_summary=(
                            "Add `actions/cache` (or setup-python/setup-node's built-in `cache:` option)."
                        ),
                    )
                )

            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get("continue-on-error") is True and any(
                    kw in str(step.get("run", "")) + str(step.get("uses", ""))
                    for kw in ("pytest", "test", "lint", "mypy", "flake8", "ruff")
                ):
                    findings.append(
                        make_finding(
                            rule_id="CICD002",
                            category=Category.CICD,
                            severity=Severity.HIGH,
                            title=f"Job '{job_name}' ignores failures in a test/lint step",
                            description=(
                                f"Step `{step.get('name', step.get('run', 'unnamed'))}` sets "
                                "`continue-on-error: true` on what looks like a test or lint step."
                            ),
                            explanation=(
                                "A CI check that cannot fail the build provides false "
                                "confidence -- the badge stays green even when tests are "
                                "actually failing."
                            ),
                            file_path=file.path,
                            suggested_fix_summary="Remove `continue-on-error` from test/lint/type-check steps.",
                        )
                    )

        has_deploy_job = any("deploy" in job_name.lower() or "release" in job_name.lower() for job_name in jobs)
        on_trigger = data.get("on") or data.get(True)
        triggers_on_push_main = False
        if isinstance(on_trigger, dict):
            push_cfg = on_trigger.get("push")
            if isinstance(push_cfg, dict):
                branches = push_cfg.get("branches") or []
                triggers_on_push_main = any(b in ("main", "master") for b in branches)
            elif push_cfg is None and "push" in on_trigger:
                triggers_on_push_main = True

        if has_deploy_job and triggers_on_push_main and "environment" not in file.content:
            findings.append(
                make_finding(
                    rule_id="CICD004",
                    category=Category.CICD,
                    severity=Severity.MEDIUM,
                    title="Deployment job has no environment protection",
                    description=(
                        "A deploy/release job runs automatically on push to main without "
                        "using a GitHub Environment for approval gating."
                    ),
                    explanation=(
                        "Without an `environment:` gate, any merge to main deploys "
                        "immediately with no manual approval step or deployment-specific "
                        "secret scoping."
                    ),
                    file_path=file.path,
                    suggested_fix_summary=(
                        "Add `environment: production` to the deploy job and require reviewers in repo settings."
                    ),
                )
            )

    return findings
