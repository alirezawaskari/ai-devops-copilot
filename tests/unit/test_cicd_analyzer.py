from app.analyzers.cicd_analyzer import analyze_cicd_setup
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_no_workflow_present_flagged():
    findings = analyze_cicd_setup([])
    assert _rule_ids(findings) == {"CICD001"}


def test_ignored_test_failures_flagged():
    content = """
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: pytest
        continue-on-error: true
"""
    findings = analyze_cicd_setup([RepoFile(path=".github/workflows/ci.yml", content=content)])
    assert "CICD002" in _rule_ids(findings)


def test_deploy_without_environment_flagged():
    content = """
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: ./deploy.sh
"""
    findings = analyze_cicd_setup([RepoFile(path=".github/workflows/deploy.yml", content=content)])
    assert "CICD004" in _rule_ids(findings)
