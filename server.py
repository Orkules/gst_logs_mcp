# -*- coding: utf-8 -*-
"""
MCP server for GStreamer debug logs. Standalone repo: no dependency on gst_logs_viewer.
Tools: get_agent_guide, list_log_files, load_log, log_summary, object_summary, query_logs.
Resource: gst-logs://agent-guide (agent instructions). Agents should get the guide first.
Time in filters: integer milliseconds from log start only (no fractions). E.g. 10000 = 10s, 10300 = 10.3s.
"""
import os
import json

from mcp.server.fastmcp import FastMCP
from core.service import (
    norm_path,
    list_log_files,
    load_log,
    get_log,
    get_lines,
    get_summary,
    get_object_summary,
)

_this_dir = os.path.dirname(os.path.abspath(__file__))
LOG_FILES_DIR = os.path.normpath(os.path.abspath(
    os.environ.get("GST_LOGS_MCP_LOG_DIR", os.path.join(_this_dir, "gst_log_files"))
))
PROJECT_ROOT = _this_dir
AGENT_GUIDE_PATH = os.path.join(_this_dir, "AGENT_GUIDE_GST_LOGS_MCP.md")

mcp = FastMCP("GStreamer Logs", json_response=True)


def _read_agent_guide():
    """Return the agent guide markdown, or a short fallback if file missing."""
    try:
        if os.path.isfile(AGENT_GUIDE_PATH):
            with open(AGENT_GUIDE_PATH, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return "# GStreamer Logs MCP – Agent Instructions\n\nAlways use filters (path, time_start, time_end, level, object_name, etc.). Prefer log_summary before query_logs. Use limit in query_logs. Load each file once."


def _opt(s):
    return (s or "").strip() or None


def _time_param(v):
    """Time: integer milliseconds from log start only (no fractions). E.g. 10000 = 10s, 10300 = 10.3s. Return None for missing/empty, else int."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = (v or "").strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _norm(path):
    if not path or not path.strip():
        return None
    return norm_path(path.strip(), PROJECT_ROOT, LOG_FILES_DIR)


@mcp.resource("gst-logs://agent-guide")
def agent_guide_resource() -> str:
    """Usage instructions and token-saving guidelines for agents. Read this when you start using the GStreamer Logs MCP so you follow the recommended workflow and filters."""
    return _read_agent_guide()


@mcp.tool()
def get_agent_guide_tool() -> str:
    """Call this first when analyzing GStreamer logs. Returns the full agent guide: usage instructions, workflow order (list → load once → summarize before query → query with filters), and token-saving rules. You must follow these instructions when using list_log_files, load_log, log_summary, object_summary, and query_logs."""
    return json.dumps({"ok": True, "guide": _read_agent_guide()})


@mcp.tool()
def list_log_files_tool(log_dir: str | None = None) -> str:
    """List GStreamer log files available. If log_dir is given, list that directory; otherwise the default log folder."""
    dir_to_use = _norm(log_dir) if log_dir and log_dir.strip() else LOG_FILES_DIR
    if not os.path.isdir(dir_to_use):
        return json.dumps({"ok": False, "error": f"Not a directory: {dir_to_use}", "files": []})
    files = list_log_files(dir_to_use)
    return json.dumps({"ok": True, "files": files, "log_dir": dir_to_use})


@mcp.tool()
def load_log_tool(path: str) -> str:
    """Load and index a GStreamer debug log file. Path can be absolute or a filename in the default log folder. Returns total lines, time_span (first/last timestamp), levels, categories, and object_count (no object list). Call once per file; later queries use the cache."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    result = load_log(resolved, PROJECT_ROOT, LOG_FILES_DIR)
    return json.dumps(result)


@mcp.tool()
def log_summary_tool(
    path: str,
    time_start: int | float | str | None = None,
    time_end: int | float | str | None = None,
    level: str | None = None,
    category: str | None = None,
    object_name: str | None = None,
    thread: str | None = None,
    function: str | None = None,
    filename: str | None = None,
    search: str | None = None,
) -> str:
    """Get counts only (no raw lines) for a loaded log, with optional filters. Returns total_matching, count_by_level, count_by_category, count_by_object. Time: integer milliseconds from log start only (e.g. 10000 = 10s, 10300 = 10.3s). Use load_log first to see time_span."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    thread_val = None
    if thread and str(thread).strip():
        try:
            thread_val = int(str(thread).strip(), 16)
        except ValueError:
            pass
    result = get_summary(
        resolved, PROJECT_ROOT, LOG_FILES_DIR,
        level=_opt(level), category=_opt(category), thread=thread_val, object_name=_opt(object_name),
        function=_opt(function), filename=_opt(filename), search=_opt(search),
        time_start=_time_param(time_start), time_end=_time_param(time_end),
    )
    return json.dumps(result)


@mcp.tool()
def object_summary_tool(
    path: str,
    category: str,
    time_start: int | float | str,
    time_end: int | float | str,
) -> str:
    """Per-level count of distinct objects and full object list in the given category and time range. Required: path, category, time_start, time_end. Time: integer milliseconds from log start only (e.g. 10000 = 10s). Call load_log first."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    if not category or not str(category).strip():
        return json.dumps({"ok": False, "error": "category is required"})
    t_start = _time_param(time_start)
    t_end = _time_param(time_end)
    if t_start is None and str(time_start).strip() != "":
        return json.dumps({"ok": False, "error": "time_start must be integer milliseconds from log start (no fractions)"})
    if t_end is None and str(time_end).strip() != "":
        return json.dumps({"ok": False, "error": "time_end must be integer milliseconds from log start (no fractions)"})
    if t_start is None or t_end is None:
        return json.dumps({"ok": False, "error": "time_start and time_end are required"})
    result = get_object_summary(resolved, PROJECT_ROOT, LOG_FILES_DIR, category=str(category).strip(), time_start=t_start, time_end=t_end)
    return json.dumps(result)


@mcp.tool()
def query_logs_tool(
    path: str,
    category: str,
    time_start: int | float | str,
    time_end: int | float | str,
    limit: int = 50,
    level: str | None = None,
    object_name: str | None = None,
    thread: str | None = None,
    function: str | None = None,
    filename: str | None = None,
    search: str | None = None,
) -> str:
    """Get log lines matching filters. Required: path, category, time_start, time_end. Time: integer milliseconds from log start only (e.g. 10000 = 10s). Optional: level, object_name, search, etc. If total_matching > 100 you get no rows, only total_matching and object_count — use log_summary first and narrow filters. limit default 50, max 2000."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    if not category or not str(category).strip():
        return json.dumps({"ok": False, "error": "category is required"})
    t_start = _time_param(time_start)
    t_end = _time_param(time_end)
    if t_start is None and str(time_start).strip() != "":
        return json.dumps({"ok": False, "error": "time_start must be integer milliseconds from log start (no fractions)"})
    if t_end is None and str(time_end).strip() != "":
        return json.dumps({"ok": False, "error": "time_end must be integer milliseconds from log start (no fractions)"})
    if t_start is None or t_end is None:
        return json.dumps({"ok": False, "error": "time_start and time_end are required"})
    log = get_log(resolved, PROJECT_ROOT, LOG_FILES_DIR)
    if not log:
        load_result = load_log(resolved, PROJECT_ROOT, LOG_FILES_DIR)
        if not load_result.get("ok"):
            return json.dumps(load_result)
    thread_val = None
    if thread and str(thread).strip():
        try:
            thread_val = int(str(thread).strip(), 16)
        except ValueError:
            pass
    result = get_lines(
        resolved, PROJECT_ROOT, LOG_FILES_DIR,
        limit=max(1, min(2000, limit)),
        time_start=t_start, time_end=t_end,
        level=_opt(level), category=_opt(category), thread=thread_val,
        object_name=_opt(object_name), function=_opt(function), filename=_opt(filename), search=_opt(search),
    )
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
