# -*- coding: utf-8 -*-
"""
MCP server for GStreamer debug logs. Standalone repo: no dependency on gst_logs_viewer.
Tools: list_log_files, load_log, log_summary, query_logs, set_base_time.
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
    set_base_time,
)

_this_dir = os.path.dirname(os.path.abspath(__file__))
LOG_FILES_DIR = os.path.normpath(os.path.abspath(
    os.environ.get("GST_LOGS_MCP_LOG_DIR", os.path.join(_this_dir, "gst_log_files"))
))
PROJECT_ROOT = _this_dir

mcp = FastMCP("GStreamer Logs", json_response=True)


def _opt(s):
    return (s or "").strip() or None


def _norm(path):
    if not path or not path.strip():
        return None
    return norm_path(path.strip(), PROJECT_ROOT, LOG_FILES_DIR)


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
    """Load and index a GStreamer debug log file. Path can be absolute or a filename in the default log folder. Returns total lines, time_span (first/last timestamp), and filter values (levels, categories, objects). Call once per file; later queries use the cache."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    result = load_log(resolved, PROJECT_ROOT, LOG_FILES_DIR)
    return json.dumps(result)


@mcp.tool()
def log_summary_tool(
    path: str,
    time_start: str | None = None,
    time_end: str | None = None,
    level: str | None = None,
    category: str | None = None,
    object_name: str | None = None,
    thread: str | None = None,
    function: str | None = None,
    filename: str | None = None,
    search: str | None = None,
) -> str:
    """Get counts only (no raw lines) for a loaded log, with optional filters. Returns total_matching, count_by_level, count_by_category, count_by_object. Use to see where errors are or how many lines match before calling query_logs. Time format: 0:00:00.000000000 or 0:00:10."""
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
        time_start=_opt(time_start), time_end=_opt(time_end),
    )
    return json.dumps(result)


@mcp.tool()
def query_logs_tool(
    path: str,
    limit: int = 500,
    time_start: str | None = None,
    time_end: str | None = None,
    level: str | None = None,
    category: str | None = None,
    object_name: str | None = None,
    thread: str | None = None,
    function: str | None = None,
    filename: str | None = None,
    search: str | None = None,
) -> str:
    """Get log lines matching filters. Log is auto-loaded if not loaded. Filters (all optional, combinable): time_start, time_end (e.g. 0:00:09, 0:00:11), level, category, object_name, thread (hex), function, filename, search (substring in message). limit caps returned lines (default 500, max 2000). Returns rows, total_matching, returned."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
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
        time_start=_opt(time_start), time_end=_opt(time_end),
        level=_opt(level), category=_opt(category), thread=thread_val,
        object_name=_opt(object_name), function=_opt(function), filename=_opt(filename), search=_opt(search),
        base_time=None,
    )
    return json.dumps(result)


@mcp.tool()
def set_base_time_tool(path: str, line_index: int) -> str:
    """Set base time for a loaded log to the timestamp of the line at line_index. After this, query_logs returns relative times for that file."""
    resolved = _norm(path)
    if not resolved:
        return json.dumps({"ok": False, "error": "Missing or invalid path"})
    result = set_base_time(resolved, PROJECT_ROOT, LOG_FILES_DIR, line_index)
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
