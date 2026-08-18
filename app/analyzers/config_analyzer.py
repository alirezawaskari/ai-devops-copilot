"""Common deployment/configuration mistakes (docker-compose, env files)."""

import re

import yaml

from app.agents.schemas import Category, Finding, Severity
from app.analyzers.base import make_finding
from app.github.schemas import RepoFile

_SECRET_KEY_RE = re.compile(r"(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)", re.IGNORECASE)
_LIKELY_REAL_SECRET_RE = re.compile(r"^[A-Za-z0-9+/_\-]{20,}$")
_PLACEHOLDER_HINTS = {"changeme", "example", "placeholder", "xxxx", "your-", "<", "replace"}


def analyze_docker_compose(file: RepoFile) -> list[Finding]:
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

        ports = service.get("ports") or []
        for port in ports:
            port_str = str(port)
            if port_str.startswith("0.0.0.0:") and any(
                db in service_name.lower() for db in ("postgres", "mysql", "db", "redis", "mongo")
            ):
                findings.append(
                    make_finding(
                        rule_id="CONF001",
                        category=Category.CONFIGURATION,
                        severity=Severity.HIGH,
                        title=f"Service '{service_name}' binds a datastore port to all interfaces",
                        description=f"`{port_str}` publishes the port on every network interface.",
                        explanation=(
                            "Datastores bound to 0.0.0.0 are reachable from outside the "
                            "host, not just from other containers on the compose network. "
                            "In cloud environments this can expose the database to the public internet."
                        ),
                        file_path=file.path,
                        evidence={"service": service_name, "port": port_str},
                        suggested_fix_summary=(
                            f'Bind to localhost only, e.g. `"127.0.0.1:{port_str.split(":")[-1]}"`, '
                            "or drop the mapping entirely."
                        ),
                    )
                )

        env = service.get("environment")
        env_items: list[tuple[str, str]] = []
        if isinstance(env, dict):
            env_items = [(k, str(v)) for k, v in env.items()]
        elif isinstance(env, list):
            for item in env:
                if isinstance(item, str) and "=" in item:
                    k, _, v = item.partition("=")
                    env_items.append((k, v))

        for key, value in env_items:
            if _SECRET_KEY_RE.search(key) and value:
                lowered = value.lower()
                looks_like_placeholder = any(hint in lowered for hint in _PLACEHOLDER_HINTS)
                looks_like_interpolation = value.startswith("${")
                if not looks_like_placeholder and not looks_like_interpolation:
                    findings.append(
                        make_finding(
                            rule_id="CONF002",
                            category=Category.CONFIGURATION,
                            severity=Severity.CRITICAL,
                            title=f"Hardcoded credential in docker-compose service '{service_name}'",
                            description=f"Environment variable `{key}` has a literal value in the compose file.",
                            explanation=(
                                "Credentials committed to docker-compose.yml are checked "
                                "into version control and shared with everyone who clones "
                                "the repository, including CI logs and forks."
                            ),
                            file_path=file.path,
                            evidence={"service": service_name, "key": key},
                            suggested_fix_summary=(
                                f"Replace with `{key}=${{{key}}}` and supply the value via a "
                                "`.env` file (git-ignored) or secrets manager."
                            ),
                        )
                    )

        if "restart" not in service:
            findings.append(
                make_finding(
                    rule_id="CONF004",
                    category=Category.CONFIGURATION,
                    severity=Severity.LOW,
                    title=f"Service '{service_name}' has no restart policy",
                    description="No `restart:` key is set for this service.",
                    explanation=(
                        "Without a restart policy, a crashed container stays down until "
                        "someone notices and manually restarts it."
                    ),
                    file_path=file.path,
                    evidence={"service": service_name},
                    suggested_fix_summary="Add `restart: unless-stopped` (or `on-failure` for one-off jobs).",
                )
            )

    return findings


def analyze_env_example(file: RepoFile) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(file.content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        value = value.strip().strip('"').strip("'")
        if not value:
            continue
        lowered = value.lower()
        if any(hint in lowered for hint in _PLACEHOLDER_HINTS):
            continue
        if _SECRET_KEY_RE.search(key) and _LIKELY_REAL_SECRET_RE.match(value):
            findings.append(
                make_finding(
                    rule_id="CONF003",
                    category=Category.CONFIGURATION,
                    severity=Severity.HIGH,
                    title=f"Committed .env.example may contain a real secret: {key}",
                    description=f"`{key}` has a high-entropy value that does not look like a placeholder.",
                    explanation=(
                        "Example env files are meant to document required variables with "
                        "placeholder values. A real-looking secret here suggests a live "
                        "credential was committed by mistake."
                    ),
                    file_path=file.path,
                    line_number=lineno,
                    evidence={"key": key},
                    suggested_fix_summary=(
                        f"Replace the value of {key} with a placeholder like `changeme`, "
                        "and rotate the credential if it was ever real."
                    ),
                )
            )
    return findings
