# GStreamer Logs MCP

MCP server for GStreamer debug logs: list files, load and index a log, get summary (counts), query lines with filters including **time range**. One load per file (cached); the agent runs many filtered queries without loading full logs into context. Standalone repo: no external project dependencies.

## Requirements

- Python 3.10+

## Install

From this directory:

```bash
pip install -r requirements.txt
```

## Run (stdio, for Cursor / Claude)

```bash
python server.py
```

Or with `uv`:

```bash
uv run server.py
```

## Configuration

| Env var | Meaning |
|--------|--------|
| `GST_LOGS_MCP_LOG_DIR` | Directory containing log files (default: `gst_log_files/` in this project). |

## Cursor

In Cursor MCP settings, add a server that runs this script, for example:

```json
{
  "mcpServers": {
    "gst-logs": {
      "command": "python",
      "args": ["C:\\path\\to\\gst_logs_mcp\\server.py"]
    }
  }
}
```

Use the path to your `gst_logs_mcp` clone and ensure the Python that has `mcp` installed is the one used by Cursor.

## Tools

| Tool | Purpose |
|------|--------|
| `list_log_files_tool` | List available log files (optionally from a given directory). |
| `load_log_tool` | Load and index a log file once; returns total, time_span (first/last), levels, categories, objects. Cached for later queries. |
| `log_summary_tool` | Counts only (no raw lines): total_matching, count_by_level, count_by_category, count_by_object. Optional filters: time_start, time_end, level, category, object_name, etc. |
| `query_logs_tool` | Get lines matching filters. Auto-loads file if needed. Filters: time_start, time_end, level, category, object_name, thread, function, filename, search. limit (default 500, max 2000). Returns rows, total_matching, returned. |
| `set_base_time_tool` | Set base time from a line index so subsequent query_logs show relative time. |

Workflow: list_log_files → load_log (or skip; query_logs auto-loads) → log_summary to see where errors are → query_logs with time range + object/level etc. to get a small slice.

## Test (no MCP client)

From project root:

```bash
python scripts/test_mcp_tools.py
```

Uses the same core as the server (list_log_files, load_log, get_summary, get_lines) and prints a short run. Optional: `GST_LOGS_MCP_LOG_DIR=/path` to point at another log directory.
