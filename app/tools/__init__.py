"""MCP-compatible analysis tool architecture.

Each `Tool` exposes a name, a natural-language description, and a JSON Schema
for its inputs -- the same shape the Model Context Protocol uses to describe
tools to an LLM. `ToolRegistry.tool_specs()` returns exactly that list, which
the agent hands to the LLM for tool selection, and `ToolRegistry.run()`
executes a chosen tool against a `RepoSnapshot`.
"""
