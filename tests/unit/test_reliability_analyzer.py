from app.analyzers.reliability_analyzer import analyze_compose_reliability, analyze_source_reliability
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_bare_except_flagged():
    content = "def f():\n    try:\n        risky()\n    except:\n        pass\n"
    findings = analyze_source_reliability(RepoFile(path="app/main.py", content=content))
    assert "REL004" in _rule_ids(findings)


def test_requests_call_without_timeout_flagged():
    content = "import requests\n\ndef f():\n    return requests.get('https://example.com')\n"
    findings = analyze_source_reliability(RepoFile(path="app/main.py", content=content))
    assert "REL005" in _rule_ids(findings)


def test_requests_call_with_timeout_not_flagged():
    content = "import requests\n\ndef f():\n    return requests.get('https://example.com', timeout=5)\n"
    findings = analyze_source_reliability(RepoFile(path="app/main.py", content=content))
    assert "REL005" not in _rule_ids(findings)


def test_compose_missing_healthcheck_and_resources_flagged():
    content = """
services:
  web:
    image: myapp
"""
    findings = analyze_compose_reliability(RepoFile(path="docker-compose.yml", content=content))
    ids = _rule_ids(findings)
    assert "REL001" in ids
    assert "REL002" in ids
