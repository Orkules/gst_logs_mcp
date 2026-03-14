# GStreamer Logs MCP – Agent Rules

Get this via `get_agent_guide_tool` or `gst-logs://agent-guide`.

**Time format:** All time filters are **integer milliseconds** from log start only (no fractions). E.g. `10000` = 10s, `10300` = 10.3s.

**You must know how many lines match before you request them.** If you call `query_logs` and the matching set is large (>100 lines), you get **zero rows** and only `total_matching`, `object_count`, and a message. Always call **log_summary** with the same filters first; narrow (time range, level, category, object_name, search) until `total_matching` is small; then call **query_logs**.

**query_logs:** **Required:** path, category, time_start, time_end (numeric). Optional: level, object_name, search. Returns rows only when total_matching ≤ 100; otherwise you get object_count and a message (if many distinct objects, narrow by object). Use limit ≤ 50 unless the user asks for more.

**object_summary:** **Required:** path, category, time_start, time_end (numeric). Returns per-level count of distinct objects and full object list. Use to discover object names, then narrow with query_logs or search.

**Workflow:** 1) list_log_files if path unknown. 2) load_log once per file → time_span, levels, categories, object_count. 3) log_summary or object_summary with filters (category + time) → get counts. 4) If total_matching is small, query_logs with same category + time (+ optional object_name/level/search).

**Checklist:** path on every call; category + time_start + time_end on query_logs and object_summary; time in integer milliseconds only; log_summary before query_logs; small limit unless user asks for more.
