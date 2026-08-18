"""OpenAI-compatible LLM client used for fix-proposal generation and summaries.

Design note: the *facts* in a `Finding` (what was found, why it matters,
severity) come from deterministic rule-based analyzers -- they are
reproducible and unit-testable without any LLM call. The LLM is used only
where judgment/generation genuinely helps: drafting a concrete patch and
writing a short human-readable executive summary.

If no usable API key is configured (`LLM_ENABLED=false` or a placeholder
key), the client falls back to deterministic templates so the API and test
suite work fully offline, without a real OpenAI account.
"""

from openai import AsyncOpenAI

from app.agents.schemas import AnalysisReport, Finding, FixProposal
from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_KEYS = {"", "sk-placeholder", "changeme"}

_FIX_SYSTEM_PROMPT = """You are a senior DevOps engineer proposing a minimal, safe fix.
Given a finding and (optionally) the surrounding file content, respond with:
1. A one-paragraph summary of the fix.
2. A unified diff (```diff fenced block) that addresses ONLY this finding.
Keep the diff minimal and focused. Never invent file content you were not shown.
"""

_SUMMARY_SYSTEM_PROMPT = """You are a senior DevOps engineer summarizing a repository analysis
for another engineer. Be concise (4-6 sentences), lead with the most severe risk, and avoid
restating every finding individually."""


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def usable(self) -> bool:
        """Whether a real LLM API key is configured (vs. offline template fallback)."""
        return self._settings.llm_enabled and self._settings.llm_api_key not in _PLACEHOLDER_KEYS

    @property
    def settings(self) -> Settings:
        return self._settings

    def raw_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self._settings.llm_api_key, base_url=self._settings.llm_base_url)

    async def generate_fix_proposal(self, finding: Finding, file_content: str | None = None) -> FixProposal:
        if not self.usable:
            return self._fallback_fix_proposal(finding)

        try:
            user_prompt = self._build_fix_prompt(finding, file_content)
            response = await self.raw_client().chat.completions.create(
                model=self._settings.llm_model,
                messages=[
                    {"role": "system", "content": _FIX_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            text = response.choices[0].message.content or ""
            summary, diff = self._parse_fix_response(text)
            if not diff:
                return self._fallback_fix_proposal(finding)
            return FixProposal(finding_rule_id=finding.rule_id, summary=summary, patch_diff=diff)
        except Exception:
            logger.exception("LLM fix generation failed, falling back to template", extra={"rule_id": finding.rule_id})
            return self._fallback_fix_proposal(finding)

    async def generate_summary(self, report: AnalysisReport) -> str:
        if not self.usable:
            return self._fallback_summary(report)

        try:
            findings_text = "\n".join(
                f"- [{f.severity.value.upper()}] {f.title} ({f.file_path or 'repo-level'})"
                for f in sorted(report.findings, key=lambda x: x.sort_key())[:25]
            )
            response = await self.raw_client().chat.completions.create(
                model=self._settings.llm_model,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Repository: {report.repo_full_name}\n\nFindings:\n{findings_text}",
                    },
                ],
                temperature=0.3,
                max_tokens=350,
            )
            return (response.choices[0].message.content or "").strip() or self._fallback_summary(report)
        except Exception:
            logger.exception("LLM summary generation failed, falling back to template")
            return self._fallback_summary(report)

    @staticmethod
    def _build_fix_prompt(finding: Finding, file_content: str | None) -> str:
        parts = [
            f"Rule: {finding.rule_id}",
            f"Title: {finding.title}",
            f"Description: {finding.description}",
            f"Why it matters: {finding.explanation}",
            f"File: {finding.file_path or 'n/a'}",
        ]
        if finding.suggested_fix_summary:
            parts.append(f"Suggested direction: {finding.suggested_fix_summary}")
        if file_content:
            parts.append(f"File content:\n```\n{file_content[:4000]}\n```")
        return "\n".join(parts)

    @staticmethod
    def _parse_fix_response(text: str) -> tuple[str, str]:
        if "```diff" in text:
            before, _, rest = text.partition("```diff")
            diff, _, _after = rest.partition("```")
            return before.strip(), diff.strip()
        if "```" in text:
            before, _, rest = text.partition("```")
            diff, _, _after = rest.partition("```")
            return before.strip(), diff.strip()
        return text.strip(), ""

    @staticmethod
    def _fallback_fix_proposal(finding: Finding) -> FixProposal:
        summary = finding.suggested_fix_summary or (
            f"Address '{finding.title}' in {finding.file_path or 'the affected file'}."
        )
        location = finding.file_path or "CHANGEME"
        line = finding.line_number or 1
        diff = (
            f"--- a/{location}\n"
            f"+++ b/{location}\n"
            f"@@ line {line} @@\n"
            f"- # TODO: manual review required\n"
            f"+ # Suggested direction: {summary}\n"
        )
        return FixProposal(finding_rule_id=finding.rule_id, summary=summary, patch_diff=diff)

    @staticmethod
    def _fallback_summary(report: AnalysisReport) -> str:
        counts = report.counts_by_severity
        top = sorted(report.findings, key=lambda f: f.sort_key())[:3]
        top_lines = "; ".join(f"{f.title} ({f.file_path or 'repo-level'})" for f in top)
        return (
            f"Analyzed {report.repo_full_name}@{report.ref} with {len(report.findings)} findings "
            f"({counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, "
            f"{counts['low']} low). Top issues: {top_lines or 'none found.'}"
        )
