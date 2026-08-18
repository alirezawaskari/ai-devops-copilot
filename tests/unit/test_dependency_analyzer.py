from app.analyzers.dependency_analyzer import (
    analyze_dependency_file,
    check_lockfile_presence,
)
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_unpinned_requirement_flagged():
    file = RepoFile(path="requirements.txt", content="flask\n")
    findings = analyze_dependency_file(file)
    assert "DEP001" in _rule_ids(findings)


def test_pinned_requirement_not_flagged_unpinned():
    file = RepoFile(path="requirements.txt", content="flask==3.0.3\n")
    findings = analyze_dependency_file(file)
    assert "DEP001" not in _rule_ids(findings)


def test_known_vulnerable_package_flagged():
    file = RepoFile(path="requirements.txt", content="pyyaml==5.0\n")
    findings = analyze_dependency_file(file)
    assert "DEP003" in _rule_ids(findings)


def test_wildcard_npm_dependency_flagged():
    file = RepoFile(path="package.json", content='{"dependencies": {"lodash": "*"}}')
    findings = analyze_dependency_file(file)
    assert "DEP005" in _rule_ids(findings)


def test_lockfile_presence_check():
    files = [RepoFile(path="requirements.txt", content="flask==3.0.3\n")]
    findings = check_lockfile_presence(files)
    assert "DEP004" in {f.rule_id for f in findings}

    files_with_lock = files + [RepoFile(path="poetry.lock", content="")]
    findings_with_lock = check_lockfile_presence(files_with_lock)
    assert "DEP004" not in {f.rule_id for f in findings_with_lock}
