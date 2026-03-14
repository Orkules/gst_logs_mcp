# GStreamer Logs MCP

MCP server for GStreamer debug logs. One load per file (cached); the agent uses **filters** (path, category, time range in ms, level, object_name, etc.) and gets **counts** before requesting lines, so context stays small. **Time:** integer milliseconds from log start only (e.g. `10000` = 10s, `10300` = 10.3s). Standalone repo: no external project dependencies.

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

## Time format

All time filters use **integer milliseconds from log start** only (no fractions). E.g. `10000` = 10s, `10300` = 10.3s. Use `load_log` first to get `time_span` so you can compute ms from the first timestamp.

## Tools

| Tool | Purpose |
|------|--------|
| **`get_agent_guide_tool`** | **Call this first.** Returns the full agent guide: workflow, filters, token-saving rules. Follow it when using the other tools. |
| `list_log_files_tool` | List available log files (optionally from a given directory). |
| `load_log_tool` | Load and index a log file once; returns total, time_span (first/last), levels, categories, object_count (no object list). Cached for later queries. |
| `log_summary_tool` | Counts only (no raw lines): total_matching, count_by_level, count_by_category, count_by_object. Optional filters: time_start, time_end (ms), level, category, object_name, etc. |
| `object_summary_tool` | **Required:** path, category, time_start, time_end (ms). Returns per-level count of distinct objects and full object list. Use to discover object names, then narrow with query_logs. |
| `query_logs_tool` | Get lines. **Required:** path, category, time_start, time_end (ms). Optional: level, object_name, search, etc. limit default 50, max 2000. If total_matching > 100 you get **no rows** — only total_matching, object_count, and a message; use log_summary first and narrow filters. |

**Resource:** `gst-logs://agent-guide` – same content as the agent guide (for clients that support MCP resources).

**Workflow:** 1) **get_agent_guide** (once). 2) list_log_files if path unknown. 3) load_log once per file → time_span, levels, categories, object_count. 4) log_summary or object_summary with filters (category + time in ms) → get counts. 5) If total_matching is small (≤100), query_logs with same category + time (+ optional object_name/level/search).

**For agents:** Call `get_agent_guide_tool` at the start, or read resource `gst-logs://agent-guide`. Full guide: [AGENT_GUIDE_GST_LOGS_MCP.md](AGENT_GUIDE_GST_LOGS_MCP.md).

## Test (no MCP client)

From project root:

```bash
python scripts/test_mcp_tools.py
```

Uses the same core as the server; prints SENT/GOT for list_log_files, load_log, log_summary (with time in ms), object_summary, query_logs. Time in tests is integer milliseconds (e.g. 0, 5000, 10500). The folder `gst_log_files/` is gitignored; set `GST_LOGS_MCP_LOG_DIR` to a directory that contains GStreamer debug logs, or add a small sample log for CI.
