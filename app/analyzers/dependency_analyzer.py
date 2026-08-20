"""Dependency risk analysis for common Python/Node manifests.

This is intentionally a small, explainable rule set rather than a full
vulnerability database integration -- it demonstrates the pattern (parse
manifest, flag unpinned/risky entries, flag known-bad ranges) without
pretending to be a real CVE feed. A production deployment would swap
`_KNOWN_VULNERABLE_RANGES` for an OSV/GitHub Advisory API call.
"""

import json
import re

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import make_finding
from app.github.schemas import RepoFile

_PIP_LINE_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(==|>=|<=|~=|!=|>|<)?\s*([A-Za-z0-9.\-*]*)")

# Illustrative examples of historically-vulnerable ranges, used to demonstrate
# the analyzer pattern. Not a substitute for a real advisory database.
_KNOWN_VULNERABLE: dict[str, str] = {
    "urllib3": "<1.24.2 has a cookie-handling vulnerability (CVE-2019-11324 class issue)",
    "pyyaml": "<5.1 allows arbitrary code execution via yaml.load (CVE-2017-18342 class issue)",
    "flask": "<1.0 has known session-handling weaknesses",
    "django": "<3.2 is past the vendor's extended support window for many CVE backports",
    "requests": "<2.20.0 has a credential-leak-on-redirect issue (CVE-2018-18074 class issue)",
    "lodash": "<4.17.21 has prototype pollution issues (CVE-2020-8203 class issue)",
    "log4j": "any version before 2.17.1 has RCE issues (Log4Shell class issue)",
}


def analyze_requirements_txt(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, raw_line in enumerate(file.content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _PIP_LINE_RE.match(line)
        if not match:
            continue
        name, operator, version = match.groups()
        normalized = name.lower()

        if not operator:
            findings.append(
                make_finding(
                    rule_id="DEP001",
                    category=Category.DEPENDENCY,
                    severity=Severity.MEDIUM,
                    title=f"Unpinned dependency: {name}",
                    description=f"`{line}` does not pin an exact version.",
                    explanation=(
                        "Unpinned dependencies mean every fresh install can resolve to a "
                        "different version, making builds non-reproducible and letting a "
                        "compromised upstream release reach production without review."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    suggested_fix_summary=f"Pin to a specific version, e.g. `{name}==<current-version>`.",
                )
            )
        elif operator in {">=", ">"}:
            findings.append(
                make_finding(
                    rule_id="DEP001B",
                    category=Category.DEPENDENCY,
                    severity=Severity.LOW,
                    title=f"Open-ended version range: {name}",
                    description=f"`{line}` allows any future version above {version}.",
                    explanation=(
                        "Open-ended ranges accept breaking or malicious future releases "
                        "automatically. A lockfile with hashes is the safer complement to "
                        "loose ranges in a manifest."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    suggested_fix_summary="Use a compatible-release pin (`~=`) or a lockfile with hashes.",
                )
            )

        if normalized in _KNOWN_VULNERABLE:
            findings.append(
                make_finding(
                    rule_id="DEP003",
                    category=Category.DEPENDENCY,
                    severity=Severity.HIGH,
                    title=f"Potentially vulnerable dependency: {name}",
                    description=_KNOWN_VULNERABLE[normalized],
                    explanation=(
                        "This package has historically had security advisories in older "
                        "version ranges. Verify the pinned version against the current "
                        "advisory database and upgrade if affected."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    evidence={
                        "package": name,
                        "declared_version": version,
                        "source": "illustrative-rule-set",
                    },
                    suggested_fix_summary=(
                        f"Upgrade {name} to the latest patched release and re-run a vulnerability scan."
                    ),
                )
            )
    return findings


def analyze_package_json(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    try:
        data = json.loads(file.content)
    except json.JSONDecodeError:
        return findings

    for section in ("dependencies", "devDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, version in deps.items():
            if version == "*" or version == "latest":
                findings.append(
                    make_finding(
                        rule_id="DEP005",
                        category=Category.DEPENDENCY,
                        severity=Severity.HIGH,
                        title=f"Wildcard dependency version: {name}",
                        description=f'"{name}": "{version}" accepts any published version.',
                        explanation=(
                            "A wildcard version means `npm install` can pull in a completely "
                            "different major version -- or a malicious release published under "
                            "a compromised maintainer account -- with zero warning."
                        ),
                        file_path=file.path,
                        suggested_fix_summary=f'Pin "{name}" to a specific version or a bounded caret range.',
                    )
                )
            if name.lower() in _KNOWN_VULNERABLE:
                findings.append(
                    make_finding(
                        rule_id="DEP003",
                        category=Category.DEPENDENCY,
                        severity=Severity.HIGH,
                        title=f"Potentially vulnerable dependency: {name}",
                        description=_KNOWN_VULNERABLE[name.lower()],
                        explanation=(
                            "This package has historically had security advisories in older "
                            "version ranges. Verify against the current advisory database."
                        ),
                        file_path=file.path,
                        evidence={
                            "package": name,
                            "declared_version": version,
                            "source": "illustrative-rule-set",
                        },
                        suggested_fix_summary=f"Upgrade {name} and re-run a vulnerability scan.",
                    )
                )

    return findings


def analyze_dependency_file(file: RepoFile) -> list[Finding]:
    basename = file.path.rsplit("/", 1)[-1].lower()
    if basename == "requirements.txt":
        return analyze_requirements_txt(file)
    if basename == "package.json":
        return analyze_package_json(file)
    return []


def check_lockfile_presence(dependency_files: list[RepoFile]) -> list[Finding]:
    paths = {f.path.rsplit("/", 1)[-1].lower() for f in dependency_files}
    findings: list[Finding] = []

    has_requirements = "requirements.txt" in paths
    has_pip_lock = "poetry.lock" in paths or "pipfile.lock" in paths
    if has_requirements and not has_pip_lock:
        findings.append(
            make_finding(
                rule_id="DEP004",
                category=Category.DEPENDENCY,
                severity=Severity.MEDIUM,
                title="No lockfile alongside requirements.txt",
                description="requirements.txt is present without poetry.lock or Pipfile.lock.",
                explanation=(
                    "Without a lockfile, transitive dependency versions are not pinned or "
                    "hash-verified, so two installs a week apart can silently differ."
                ),
                suggested_fix_summary="Adopt pip-tools, Poetry, or Pipenv to generate and commit a lockfile.",
            )
        )

    has_package_json = "package.json" in paths
    has_node_lock = any(name in paths for name in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"))
    if has_package_json and not has_node_lock:
        findings.append(
            make_finding(
                rule_id="DEP004B",
                category=Category.DEPENDENCY,
                severity=Severity.MEDIUM,
                title="No lockfile alongside package.json",
                description="package.json is present without package-lock.json, yarn.lock, or pnpm-lock.yaml.",
                explanation=(
                    "Without a committed lockfile, `npm install` can resolve different "
                    "transitive versions across machines and CI runs."
                ),
                suggested_fix_summary="Commit the lockfile generated by your package manager.",
            )
        )

    return findings
