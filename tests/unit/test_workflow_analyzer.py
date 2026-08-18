from app.analyzers.workflow_analyzer import analyze_workflow
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_flags_pull_request_target_with_pr_head_checkout():
    content = """
name: CI
on:
  pull_request_target:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.event.pull_request.head.sha }}
"""
    findings = analyze_workflow(RepoFile(path=".github/workflows/ci.yml", content=content))
    assert "GHA001" in _rule_ids(findings)


def test_flags_unpinned_action():
    content = """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    findings = analyze_workflow(RepoFile(path=".github/workflows/ci.yml", content=content))
    assert "GHA002" in _rule_ids(findings)


def test_sha_pinned_action_not_flagged():
    content = """
name: CI
on: push
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8f4b7f84864484a7bf31766abe9204da3cbe65b3
"""
    findings = analyze_workflow(RepoFile(path=".github/workflows/ci.yml", content=content))
    assert "GHA002" not in _rule_ids(findings)


def test_flags_secret_echo():
    content = """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo "token is ${{ secrets.DEPLOY_TOKEN }}"
"""
    findings = analyze_workflow(RepoFile(path=".github/workflows/ci.yml", content=content))
    assert "GHA003" in _rule_ids(findings)


def test_flags_missing_permissions_block():
    content = """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
    findings = analyze_workflow(RepoFile(path=".github/workflows/ci.yml", content=content))
    assert "GHA004B" in _rule_ids(findings)


def test_invalid_yaml_produces_parse_finding():
    content = "not: [valid yaml"
    findings = analyze_workflow(RepoFile(path=".github/workflows/broken.yml", content=content))
    assert _rule_ids(findings) == {"GHA000"}
