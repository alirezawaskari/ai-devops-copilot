"""Prompt text used for LLM-assisted tool selection.

Deterministic applicability checks (`Tool.applies_to`) are the default and
recommended path -- they're fast, free, and fully testable offline. This
prompt exists to support an optional LLM-driven selection mode
(`DevOpsAgent(tool_selection_mode="llm")`) that demonstrates genuine
tool-calling reasoning for repositories where applicability is ambiguous.
"""

TOOL_SELECTION_SYSTEM_PROMPT = """You are a DevOps analysis planner. Given a summary of a
repository's structure and a list of available analysis tools (each with a name and
description), choose which tools are worth running. Respond with a JSON array of tool
names only, e.g. ["analyze_dockerfiles", "analyze_dependency_risk"]. Only include tools
whose description clearly applies to the repository summary provided."""
