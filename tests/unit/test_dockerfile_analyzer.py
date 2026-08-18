from app.analyzers.dockerfile_analyzer import analyze_dockerfile
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_flags_unpinned_base_image():
    file = RepoFile(path="Dockerfile", content='FROM python\nCMD ["python", "app.py"]\n')
    findings = analyze_dockerfile(file)
    assert "DOCKER001" in _rule_ids(findings)


def test_pinned_base_image_not_flagged():
    file = RepoFile(
        path="Dockerfile",
        content=(
            "FROM python:3.12.1-slim\nUSER appuser\n"
            "HEALTHCHECK CMD curl -f http://localhost/ || exit 1\n"
            'EXPOSE 8000\nCMD ["python", "app.py"]\n'
        ),
    )
    findings = analyze_dockerfile(file)
    assert "DOCKER001" not in _rule_ids(findings)


def test_flags_missing_user_instruction():
    file = RepoFile(path="Dockerfile", content='FROM python:3.12.1-slim\nCMD ["python", "app.py"]\n')
    findings = analyze_dockerfile(file)
    assert "DOCKER002" in _rule_ids(findings)
    doc002 = next(f for f in findings if f.rule_id == "DOCKER002")
    assert doc002.severity.value == "high"


def test_flags_secret_in_env():
    file = RepoFile(
        path="Dockerfile",
        content="FROM python:3.12.1-slim\nENV DATABASE_PASSWORD=hunter2\nUSER appuser\n",
    )
    findings = analyze_dockerfile(file)
    assert "DOCKER004" in _rule_ids(findings)
    finding = next(f for f in findings if f.rule_id == "DOCKER004")
    assert finding.severity.value == "critical"


def test_flags_curl_pipe_bash():
    file = RepoFile(
        path="Dockerfile",
        content="FROM python:3.12.1-slim\nRUN curl -sSL https://example.com/install.sh | bash\nUSER appuser\n",
    )
    findings = analyze_dockerfile(file)
    assert "DOCKER009" in _rule_ids(findings)


def test_flags_add_for_local_files():
    file = RepoFile(path="Dockerfile", content="FROM python:3.12.1-slim\nADD . /app\nUSER appuser\n")
    findings = analyze_dockerfile(file)
    assert "DOCKER003" in _rule_ids(findings)


def test_flags_missing_healthcheck_and_expose():
    file = RepoFile(path="Dockerfile", content='FROM python:3.12.1-slim\nUSER appuser\nCMD ["python"]\n')
    findings = analyze_dockerfile(file)
    ids = _rule_ids(findings)
    assert "DOCKER006" in ids
    assert "DOCKER008" in ids


def test_scratch_base_image_not_flagged_for_pinning():
    file = RepoFile(path="Dockerfile", content="FROM scratch\nUSER appuser\n")
    findings = analyze_dockerfile(file)
    assert "DOCKER001" not in _rule_ids(findings)
