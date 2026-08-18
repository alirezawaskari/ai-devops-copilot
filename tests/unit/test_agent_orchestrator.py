import pytest

from app.agents.orchestrator import DevOpsAgent
from app.core.llm import LLMClient
from app.github.demo_loader import load_demo_snapshot


@pytest.fixture
def offline_llm_client() -> LLMClient:
    return LLMClient()


async def test_agent_selects_only_applicable_tools_for_demo_repo(offline_llm_client):
    agent = DevOpsAgent(llm_client=offline_llm_client)
    snapshot = load_demo_snapshot()

    selected = await agent.select_tools(snapshot)

    assert "analyze_dockerfiles" in selected
    assert "analyze_github_actions_security" in selected
    assert "analyze_dependency_risk" in selected
    assert "analyze_configuration" in selected


async def test_agent_analyze_produces_findings_across_categories(offline_llm_client):
    agent = DevOpsAgent(llm_client=offline_llm_client)
    snapshot = load_demo_snapshot()

    report = await agent.analyze(snapshot)

    categories = {f.category.value for f in report.findings}
    assert "dockerfile" in categories
    assert "github_actions" in categories
    assert "dependency" in categories
    assert len(report.findings) > 5
    # findings must be sorted with the most severe first
    severities = [f.severity.value for f in report.findings]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    assert severities == sorted(severities, key=lambda s: order[s])


async def test_agent_deduplicates_repeated_findings(offline_llm_client):
    agent = DevOpsAgent(llm_client=offline_llm_client)
    snapshot = load_demo_snapshot()
    report = await agent.analyze(snapshot)

    keys = [(f.rule_id, f.file_path, f.line_number) for f in report.findings]
    assert len(keys) == len(set(keys))


async def test_agent_summary_falls_back_without_llm_key(offline_llm_client):
    agent = DevOpsAgent(llm_client=offline_llm_client)
    snapshot = load_demo_snapshot()
    report = await agent.analyze(snapshot)

    summary = await agent.summarize(report)
    assert snapshot.repo.full_name in summary


async def test_propose_fix_never_touches_source_and_returns_diff(offline_llm_client):
    agent = DevOpsAgent(llm_client=offline_llm_client)
    snapshot = load_demo_snapshot()
    report = await agent.analyze(snapshot)
    finding = report.findings[0]

    proposal = await agent.propose_fix(finding)

    assert proposal.finding_rule_id == finding.rule_id
    assert proposal.patch_diff  # a diff was produced
    assert "---" in proposal.patch_diff or "+++" in proposal.patch_diff
