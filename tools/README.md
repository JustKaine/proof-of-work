# tools/ — MCP Tool Plugins

This directory contains the 7 MCP tools that are dynamically loaded by `server.py` at startup. Each file exports a `TOOL_DEF` dict that registers the tool with FastMCP.

For user-facing workflow, usage examples, job description file guidance, and user instructions, see the root [USE_README.md](../USE_README.md).

## Tool Plugins

Each tool file must export a `TOOL_DEF` dict:

```python
def my_handler(param1: str, param2: int = 0) -> dict[str, Any]:
  """Tool handler — does the work and returns a result dict."""
  payload = {"param1": param1, "param2": param2}
  # Validate input against contracts
  # Build result dict
  # Return via engine.session.finalize_tool_response()
  ...

TOOL_DEF = {
  "name": "my_tool",                      # MCP tool name
  "description": "What this tool does.",   # Shown to the client
  "handler": my_handler,                   # Callable
}
```

`server.py` scans the tools directory for `*.py` files, imports each, extracts `TOOL_DEF`, and registers the handler with FastMCP. The tool's parent directory is added to `sys.path` so imports like `from engine.audit import log_event` work.

## Tool Summary

| Tool           | Purpose                                                            |
| -------------- | ------------------------------------------------------------------ |
| `analyze_jd`   | Extract and prioritize requirements from 1–3 job descriptions      |
| `map_resume`   | Map resume evidence to JD requirements; score gaps, detect shifts  |
| `draft_resume` | Generate a tagged draft with provenance labels and verification Qs |
| `finalize`     | Produce the final resume after all verification items are resolved |
| `identify_user`| Set user identity for persistent skill profiles                   |
| `manage_skills`| Add, list, or remove supplemental skills in user profile          |
| `faq`          | Answer questions about workflow, folder layout, policies, etc.     |
