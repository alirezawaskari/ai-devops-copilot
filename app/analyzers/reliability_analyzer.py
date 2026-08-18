"""Obvious reliability problems in application source code and deployment config."""

import re

import yaml

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import make_finding
from app.github.schemas import RepoFile

_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$")
_REQUESTS_CALL_RE = re.compile(r"requests\.(get|post|put|delete|patch|head)\s*\(")


def analyze_source_reliability(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    lines = file.content.splitlines()

    for lineno, line in enumerate(lines, start=1):
        if _BARE_EXCEPT_RE.match(line):
            next_nonblank = next(
                (subsequent.strip() for subsequent in lines[lineno : lineno + 3] if subsequent.strip()),
                "",
            )
            if next_nonblank in {"pass", "continue", "..."}:
                findings.append(
                    make_finding(
                        rule_id="REL004",
                        category=Category.RELIABILITY,
                        severity=Severity.MEDIUM,
                        title="Bare except silently swallows all errors",
                        description=f"{file.path}:{lineno} catches every exception and discards it.",
                        explanation=(
                            "A bare `except: pass` hides bugs, including KeyboardInterrupt "
                            "and SystemExit, making failures invisible until their downstream "
                            "effects surface much later and are far harder to trace."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        suggested_fix_summary="Catch specific exceptions and at minimum log them before continuing.",
                    )
                )

        if _REQUESTS_CALL_RE.search(line) and "timeout=" not in line:
            # allow a timeout on the following couple of lines for multi-line calls
            lookahead = " ".join(lines[lineno - 1 : lineno + 2])
            if "timeout=" not in lookahead:
                findings.append(
                    make_finding(
                        rule_id="REL005",
                        category=Category.RELIABILITY,
                        severity=Severity.MEDIUM,
                        title="Outbound HTTP call has no timeout",
                        description=f"{file.path}:{lineno} calls `requests.*` without a `timeout=`.",
                        explanation=(
                            "Without a timeout, a hung upstream service blocks the calling "
                            "thread/worker indefinitely, which can cascade into full service "
                            "unavailability under load."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        suggested_fix_summary="Add an explicit timeout, e.g. `requests.get(url, timeout=5)`.",
                    )
                )

    return findings


def analyze_compose_reliability(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    try:
        data = yaml.safe_load(file.content)
    except yaml.YAMLError:
        return findings
    if not isinstance(data, dict):
        return findings

    services = data.get("services") or {}
    if not isinstance(services, dict):
        return findings

    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        if "healthcheck" not in service:
            findings.append(
                make_finding(
                    rule_id="REL001",
                    category=Category.RELIABILITY,
                    severity=Severity.LOW,
                    title=f"Service '{service_name}' has no healthcheck",
                    description="No `healthcheck:` block is defined for this service.",
                    explanation=(
                        "Without a healthcheck, `depends_on` cannot wait for the service to "
                        "be truly ready, and Compose/orchestrators cannot detect a hung-but-running container."
                    ),
                    file_path=file.path,
                    evidence={"service": service_name},
                    suggested_fix_summary="Add a healthcheck that probes the service's readiness endpoint.",
                )
            )

        deploy = service.get("deploy") or {}
        resources = deploy.get("resources") if isinstance(deploy, dict) else None
        if not resources:
            findings.append(
                make_finding(
                    rule_id="REL002",
                    category=Category.RELIABILITY,
                    severity=Severity.LOW,
                    title=f"Service '{service_name}' has no resource limits",
                    description="No `deploy.resources.limits` are configured.",
                    explanation=(
                        "Without CPU/memory limits, a single misbehaving service can "
                        "exhaust host resources and take down every other container "
                        "on the same host."
                    ),
                    file_path=file.path,
                    evidence={"service": service_name},
                    suggested_fix_summary="Set `deploy.resources.limits.memory` / `.cpus` for each service.",
                )
            )

    return findings
