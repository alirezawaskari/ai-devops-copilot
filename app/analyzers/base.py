"""Shared helpers for rule-based analyzers."""

from app.agents.schemas import Category, Finding, Severity


def make_finding(
    *,
    rule_id: str,
    category: Category,
    severity: Severity,
    title: str,
    description: str,
    explanation: str,
    file_path: str | None = None,
    line_number: int | None = None,
    evidence: dict | None = None,
    suggested_fix_summary: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        title=title,
        description=description,
        explanation=explanation,
        file_path=file_path,
        line_number=line_number,
        evidence=evidence or {},
        suggested_fix_summary=suggested_fix_summary,
    )


def find_line_number(content: str, needle: str) -> int | None:
    for idx, line in enumerate(content.splitlines(), start=1):
        if needle in line:
            return idx
    return None
