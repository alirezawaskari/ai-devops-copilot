"""Dockerfile security and optimization analysis."""

import re

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import find_line_number, make_finding
from app.github.schemas import RepoFile

_FROM_RE = re.compile(r"^\s*FROM\s+([^\s]+)(\s+AS\s+\S+)?", re.IGNORECASE)
_USER_RE = re.compile(r"^\s*USER\s+", re.IGNORECASE)
_ADD_RE = re.compile(r"^\s*ADD\s+", re.IGNORECASE)
_RUN_RE = re.compile(r"^\s*RUN\s+(.*)", re.IGNORECASE)
_HEALTHCHECK_RE = re.compile(r"^\s*HEALTHCHECK\s+", re.IGNORECASE)
_SECRET_ENV_RE = re.compile(
    r"^\s*(ENV|ARG)\s+([A-Z0-9_]*(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*=?",
    re.IGNORECASE,
)


def analyze_dockerfile(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    content = file.content
    lines = content.splitlines()

    for lineno, line in enumerate(lines, start=1):
        from_match = _FROM_RE.match(line)
        if from_match:
            image_ref = from_match.group(1)
            if image_ref.lower() == "scratch":
                continue
            if ":" not in image_ref or image_ref.endswith(":latest"):
                findings.append(
                    make_finding(
                        rule_id="DOCKER001",
                        category=Category.DOCKERFILE,
                        severity=Severity.MEDIUM,
                        title="Base image is not pinned to a specific version",
                        description=(f"`FROM {image_ref}` does not pin a specific, immutable tag (or uses `:latest`)."),
                        explanation=(
                            "Unpinned base images make builds non-reproducible: the same "
                            "Dockerfile can produce a different image tomorrow, silently "
                            "pulling in breaking changes or new vulnerabilities."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        evidence={"line": line.strip()},
                        suggested_fix_summary="Pin the base image to a specific version tag (and ideally a digest).",
                    )
                )

        if _ADD_RE.match(line) and "http://" not in line and "https://" not in line:
            findings.append(
                make_finding(
                    rule_id="DOCKER003",
                    category=Category.DOCKERFILE,
                    severity=Severity.LOW,
                    title="ADD used instead of COPY for local files",
                    description=f"`{line.strip()}` uses ADD for what appears to be a local file.",
                    explanation=(
                        "ADD has implicit behaviors (auto-extracting archives, fetching "
                        "remote URLs) that make Dockerfiles harder to reason about. COPY "
                        "is the explicit, predictable choice for local files."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    evidence={"line": line.strip()},
                    suggested_fix_summary="Replace ADD with COPY unless you need archive extraction or a remote URL.",
                )
            )

        secret_match = _SECRET_ENV_RE.match(line)
        if secret_match:
            findings.append(
                make_finding(
                    rule_id="DOCKER004",
                    category=Category.DOCKERFILE,
                    severity=Severity.CRITICAL,
                    title="Possible secret baked into the image",
                    description=(f"`{line.strip()}` sets what looks like a credential via {secret_match.group(1)}."),
                    explanation=(
                        "ENV and ARG values are stored in the image layer history and are "
                        "visible to anyone with `docker history` access, even after being "
                        "'overwritten' in a later layer. Secrets baked in this way leak."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    evidence={"line": line.strip()},
                    suggested_fix_summary=(
                        "Remove the credential from the Dockerfile and inject it at runtime "
                        "via a secrets manager, `docker run --env-file`, or BuildKit secret mounts."
                    ),
                )
            )

        run_match = _RUN_RE.match(line)
        if run_match:
            run_body = run_match.group(1)
            if re.search(r"curl[^\n|]*\|\s*(sudo\s+)?(bash|sh)\b", run_body) or re.search(
                r"wget[^\n|]*\|\s*(sudo\s+)?(bash|sh)\b", run_body
            ):
                findings.append(
                    make_finding(
                        rule_id="DOCKER009",
                        category=Category.DOCKERFILE,
                        severity=Severity.CRITICAL,
                        title="Piping a remote download directly into a shell",
                        description=f"`{line.strip()}` pipes curl/wget output straight into bash/sh.",
                        explanation=(
                            "This pattern executes unreviewed, unpinned remote code during "
                            "the build with no integrity verification. If the remote host or "
                            "connection is compromised, the build is compromised."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        evidence={"line": line.strip()},
                        suggested_fix_summary=(
                            "Download the script, pin it to a checksum, review it, then execute it explicitly."
                        ),
                    )
                )
            if "apt-get install" in run_body and "--no-install-recommends" not in run_body:
                findings.append(
                    make_finding(
                        rule_id="DOCKER005",
                        category=Category.DOCKERFILE,
                        severity=Severity.LOW,
                        title="apt-get install without --no-install-recommends",
                        description=f"`{line.strip()}` installs packages without limiting recommended extras.",
                        explanation=(
                            "Installing recommended-but-not-required packages bloats the "
                            "image size and widens the attack surface for no functional benefit."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        evidence={"line": line.strip()},
                        suggested_fix_summary=(
                            "Add --no-install-recommends and clean up apt lists in the same RUN layer."
                        ),
                    )
                )
            if "apt-get install" in run_body and "rm -rf /var/lib/apt/lists" not in content:
                findings.append(
                    make_finding(
                        rule_id="DOCKER005B",
                        category=Category.DOCKERFILE,
                        severity=Severity.LOW,
                        title="apt cache not cleaned up after install",
                        description="apt-get install is used but the apt list cache is never removed.",
                        explanation=(
                            "Leftover apt metadata is dead weight in every layer beneath it, "
                            "permanently increasing final image size even if later layers "
                            "delete the files at a different path."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        evidence={"line": line.strip()},
                        suggested_fix_summary="Append `&& rm -rf /var/lib/apt/lists/*` to the same RUN instruction.",
                    )
                )
            if re.search(r"\bsudo\b", run_body):
                findings.append(
                    make_finding(
                        rule_id="DOCKER010",
                        category=Category.DOCKERFILE,
                        severity=Severity.MEDIUM,
                        title="sudo used inside container build",
                        description=f"`{line.strip()}` invokes sudo.",
                        explanation=(
                            "Containers typically run as root during build already; sudo "
                            "usually indicates copy-pasted host instructions and adds an "
                            "unnecessary package (sudo itself) to the final image."
                        ),
                        file_path=file.path,
                        line_number=lineno,
                        evidence={"line": line.strip()},
                        suggested_fix_summary="Drop sudo; the build already runs as root unless USER was set earlier.",
                    )
                )

    if not any(_USER_RE.match(line) for line in lines):
        findings.append(
            make_finding(
                rule_id="DOCKER002",
                category=Category.DOCKERFILE,
                severity=Severity.HIGH,
                title="Container runs as root (no USER instruction)",
                description="No USER instruction was found, so the container runs as root by default.",
                explanation=(
                    "Running as root means a container-breakout vulnerability grants the "
                    "attacker root on the host's container runtime namespace. Least-privilege "
                    "containers run as a dedicated non-root user."
                ),
                file_path=file.path,
                suggested_fix_summary=(
                    "Create a non-root user and switch to it with USER before the final CMD/ENTRYPOINT."
                ),
            )
        )

    if not any(_HEALTHCHECK_RE.match(line) for line in lines):
        findings.append(
            make_finding(
                rule_id="DOCKER006",
                category=Category.DOCKERFILE,
                severity=Severity.LOW,
                title="No HEALTHCHECK defined",
                description="The Dockerfile does not declare a HEALTHCHECK instruction.",
                explanation=(
                    "Without a HEALTHCHECK, orchestrators (Docker, Compose, Kubernetes via "
                    "readiness probes) cannot automatically detect and restart a hung "
                    "container that is still 'running' but no longer serving traffic."
                ),
                file_path=file.path,
                suggested_fix_summary="Add a HEALTHCHECK instruction that curls a lightweight health endpoint.",
            )
        )

    if not re.search(r"^\s*EXPOSE\s+", content, re.MULTILINE):
        line_no = find_line_number(content, "CMD") or find_line_number(content, "ENTRYPOINT")
        findings.append(
            make_finding(
                rule_id="DOCKER008",
                category=Category.DOCKERFILE,
                severity=Severity.LOW,
                title="No EXPOSE instruction",
                description="The Dockerfile does not document which port the service listens on.",
                explanation=(
                    "EXPOSE is documentation-only but its absence makes the image's network "
                    "contract implicit, forcing operators to read application code to find "
                    "the listening port."
                ),
                file_path=file.path,
                line_number=line_no,
                suggested_fix_summary="Add an EXPOSE instruction documenting the service's listening port.",
            )
        )

    return findings
