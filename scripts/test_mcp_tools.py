#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the GStreamer Logs MCP tools logic.
Prints SENT / GOT for each call. Run from project root:

  python scripts/test_mcp_tools.py
"""
import os
import sys
import json

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_scripts_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.service import (
    list_log_files,
    load_log,
    get_log,
    get_lines,
    get_summary,
    get_object_summary,
)

LOG_FILES_DIR = os.path.normpath(os.path.abspath(
    os.environ.get("GST_LOGS_MCP_LOG_DIR", os.path.join(_project_root, "gst_log_files"))
))


def show(name, sent, got):
    print("=" * 60)
    print(" ", name)
    print("-" * 60)
    print("SENT:", json.dumps(sent, ensure_ascii=False, default=str))
    print("-" * 60)
    if isinstance(got, dict):
        if got.get("rows") and len(got["rows"]) > 5:
            truncated = got.copy()
            truncated["rows"] = got["rows"][:5]
            truncated["_rows_truncated"] = len(got["rows"]) - 5
            print("GOT:", json.dumps(truncated, ensure_ascii=False, default=str, indent=2))
        else:
            print("GOT:", json.dumps(got, ensure_ascii=False, default=str, indent=2))
    else:
        print("GOT:", got)
    print()


def main():
    print("GStreamer Logs MCP – tool test (SENT / GOT)")
    print("Log dir:", LOG_FILES_DIR)
    print()

    # 1) list_log_files
    sent = {"log_dir": LOG_FILES_DIR}
    files = list_log_files(LOG_FILES_DIR)
    if not files:
        show("list_log_files", sent, {"error": "No files", "files": []})
        return 1
    got = {"ok": True, "files": [f["name"] for f in files], "count": len(files)}
    show("list_log_files", sent, got)
    path = files[0]["path"]

    # 2) load_log
    sent = {"path": path}
    result = load_log(path, _project_root, LOG_FILES_DIR)
    if not result.get("ok"):
        show("load_log", sent, result)
        return 1
    show("load_log", sent, result)

    # 3) log_summary (no filters)
    sent = {"path": path}
    summary = get_summary(path, _project_root, LOG_FILES_DIR)
    show("log_summary (no filters)", sent, summary)
    if not summary.get("ok"):
        return 1

    # 4) log_summary with time in milliseconds (0 ms to 10500 ms = 10.5s)
    sent = {"path": path, "time_start": 0, "time_end": 10500}
    summary_t = get_summary(path, _project_root, LOG_FILES_DIR, time_start=0, time_end=10500)
    show("log_summary (time_start=0, time_end=10500 ms)", sent, summary_t)

    # 5) log_summary with category + time (ms)
    categories = result.get("categories") or []
    cat = categories[0] if categories else None
    sent = {"path": path, "category": cat, "time_start": 0, "time_end": 5000}
    summary_c = get_summary(path, _project_root, LOG_FILES_DIR, category=cat, time_start=0, time_end=5000) if cat else {"ok": False, "error": "no category"}
    show("log_summary (category + time)", sent, summary_c)

    # 6) object_summary: required category + time (ms)
    if cat:
        sent = {"path": path, "category": cat, "time_start": 0, "time_end": 5000}
        obj_sum = get_object_summary(path, _project_root, LOG_FILES_DIR, category=cat, time_start=0, time_end=5000)
        show("object_summary (category + time)", sent, obj_sum)
    else:
        print("=" * 60)
        print(" object_summary – skipped (no category)")
        print()

    # 7) query_logs with category + time (ms) and limit
    sent = {"path": path, "category": cat, "time_start": 0, "time_end": 2000, "limit": 5}
    lines_result = (
        get_lines(path, _project_root, LOG_FILES_DIR, category=cat, time_start=0, time_end=2000, limit=5)
        if cat else {"ok": False, "error": "category required"}
    )
    show("query_logs (category + time + limit)", sent, lines_result)

    # 8) query_logs without category (service allows it; server would reject)
    sent = {"path": path, "time_start": 0, "time_end": 1000, "limit": 3}
    lines_no_cat = get_lines(path, _project_root, LOG_FILES_DIR, time_start=0, time_end=1000, limit=3)
    show("query_logs (no category)", sent, lines_no_cat)

    # 9) query_logs with optional object_name (time in ms)
    if summary_c.get("ok") and summary_c.get("count_by_object"):
        first_obj = next(iter(summary_c["count_by_object"].keys()), None)
        if first_obj and cat:
            sent = {"path": path, "category": cat, "time_start": 0, "time_end": 5000, "object_name": first_obj, "limit": 3}
            lines_obj = get_lines(path, _project_root, LOG_FILES_DIR, category=cat, time_start=0, time_end=5000, object_name=first_obj, limit=3)
            show("query_logs (category + time + object_name)", sent, lines_obj)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
