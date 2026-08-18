"""Rule-based static analyzers.

Each analyzer is a pure function: `list[RepoFile] -> list[Finding]`. They are
deterministic and unit-testable in isolation, independent of the LLM. The
agent layer invokes them as tools and uses the LLM to prioritize, explain
findings in context, and draft fix diffs -- the LLM is never relied on to
invent the underlying facts.
"""
