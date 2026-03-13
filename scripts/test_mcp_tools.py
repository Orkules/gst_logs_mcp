#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the GStreamer Logs MCP tools logic.
Runs against the core service (no MCP transport). Use from project root:

  python scripts/test_mcp_tools.py

Or with a specific log dir:

  GST_LOGS_MCP_LOG_DIR=/path/to/logs python scripts/test_mcp_tools.py
"""
import os
import sys

# Project root = parent of scripts/
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_scripts_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.service import (
    norm_path,
    list_log_files,
    load_log,
    get_log,
    get_lines,
    get_summary,
)

LOG_FILES_DIR = os.path.normpath(os.path.abspath(
    os.environ.get("GST_LOGS_MCP_LOG_DIR", os.path.join(_project_root, "gst_log_files"))
))


def main():
    print("GStreamer Logs MCP – tool test")
    print("Log dir:", LOG_FILES_DIR)
    print()

    # 1) list_log_files
    files = list_log_files(LOG_FILES_DIR)
    if not files:
        print("No log files in", LOG_FILES_DIR)
        return 1
    print("list_log_files:", len(files), "file(s)", [f["name"] for f in files[:5]])
    path = files[0]["path"]
    print("Using file:", path)
    print()

    # 2) load_log
    result = load_log(path, _project_root, LOG_FILES_DIR)
    if not result.get("ok"):
        print("load_log failed:", result.get("error"))
        return 1
    print("load_log: ok, total =", result["total"], ", time_span =", result.get("time_span"))
    print("  levels (sample):", result["levels"][:5] if len(result["levels"]) > 5 else result["levels"])
    print("  objects (sample):", result["objects"][:8] if len(result["objects"]) > 8 else result["objects"])
    print()

    # 3) log_summary (no filters)
    summary = get_summary(path, _project_root, LOG_FILES_DIR)
    if not summary.get("ok"):
        print("get_summary failed:", summary.get("error"))
        return 1
    print("log_summary (no filters): total_matching =", summary["total_matching"])
    print("  count_by_level:", summary["count_by_level"])
    print()

    # 4) log_summary with level=ERROR (if any)
    summary_err = get_summary(path, _project_root, LOG_FILES_DIR, level="ERROR")
    if summary_err.get("ok"):
        print("log_summary(level=ERROR): total_matching =", summary_err["total_matching"])
    print()

    # 5) query_logs with limit
    lines_result = get_lines(path, _project_root, LOG_FILES_DIR, limit=3)
    if not lines_result.get("ok"):
        print("get_lines failed:", lines_result.get("error"))
        return 1
    print("query_logs(limit=3): total_matching =", lines_result["total_matching"], ", returned =", lines_result["returned"])
    for i, row in enumerate(lines_result["rows"]):
        print("  ", i + 1, row.get("time"), row.get("level"), row.get("object") or "", (row.get("message") or "")[:60])
    print()

    # 6) query_logs with time range (first few seconds) if we have time_span
    t0 = result.get("time_span", {}).get("first", "")
    if t0:
        # ask for first 1 second: 0:00:00.0 to 0:00:01.0
        lines_win = get_lines(path, _project_root, LOG_FILES_DIR, time_start="0:00:00.000000000", time_end="0:00:01.000000000", limit=5)
        if lines_win.get("ok"):
            print("query_logs(time 0..1s, limit=5): total_matching =", lines_win["total_matching"], ", returned =", lines_win["returned"])
    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
