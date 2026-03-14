# -*- coding: utf-8 -*-
"""Log API: path resolution, log cache, filtering, row building."""

import os

from core.parser import LogFile, DebugLevel, time_args


_log_cache = {}
_search_cache = {}
_search_cache_order = []
_SEARCH_CACHE_MAX = 64

# If total_matching > this, query_logs returns no rows — only total_matching, object_count, and message.
MAX_MATCHING_TO_RETURN_ROWS = 100
# If distinct object count > this, message tells agent to narrow by object.
MAX_OBJECTS_SUGGEST_NARROW = 30


def norm_path(raw_path, project_root, log_files_dir):
    if not raw_path or not raw_path.strip():
        return None
    p = raw_path.strip()
    if os.path.isabs(p):
        return os.path.normpath(os.path.abspath(p))
    if os.path.sep not in p and (os.path.altsep or "") not in p:
        p = os.path.join(log_files_dir, p)
    else:
        p = os.path.join(project_root, p)
    return os.path.normpath(os.path.abspath(p))


def list_log_files(log_files_dir):
    if not os.path.isdir(log_files_dir):
        return []
    files = []
    for name in sorted(os.listdir(log_files_dir)):
        path = os.path.join(log_files_dir, name)
        if os.path.isfile(path):
            files.append({"name": name, "path": os.path.normpath(os.path.abspath(path))})
    return files


def load_log(path, project_root, log_files_dir):
    path = norm_path(path, project_root, log_files_dir) if not os.path.isabs(path or "") else path
    if not path or not os.path.isfile(path):
        return {"ok": False, "error": "File not found"}
    _clear_search_cache_for_path(path)
    try:
        log = LogFile(path)
        _log_cache[path] = log
        t0, t1 = log.time_span
        return {
            "ok": True,
            "path": path,
            "total": len(log),
            "time_span": {"first": time_args(t0), "last": time_args(t1)},
            "levels": log.level_names,
            "categories": log.category_names,
            "object_count": len(log.object_names),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _clear_search_cache_for_path(path):
    global _search_cache, _search_cache_order
    to_del = [k for k in _search_cache if k[0] == path]
    for k in to_del:
        _search_cache.pop(k, None)
        if k in _search_cache_order:
            _search_cache_order.remove(k)


def _time_ms_to_ns(log, time_ms):
    """Convert milliseconds from log start (integer only) to absolute ns."""
    if time_ms is None:
        return None
    try:
        ms = int(time_ms)
    except (TypeError, ValueError):
        return None
    return log.time_span[0] + ms * 1_000_000


def _get_filtered_indices(path, log, level, category, thread, obj, function, filename, search, time_start=None, time_end=None):
    # time_start/time_end: integer milliseconds from log start (no fractions)
    time_min = _time_ms_to_ns(log, time_start)
    time_max = _time_ms_to_ns(log, time_end)
    base = log.get_filtered_indices(
        level=level, category=category, thread=thread, object_name=obj, function=function, filename=filename,
        time_min=time_min, time_max=time_max,
    )
    if not search:
        return base
    key = (path, level or "", category or "", thread, obj or "", function or "", filename or "", search or "", time_start, time_end)
    if key not in _search_cache:
        search_bytes = search.encode("utf8")
        indices = []
        for i in base:
            line = log.get_line(i)
            msg = line[9]
            if isinstance(msg, str):
                msg = msg.encode("utf8", errors="replace")
            if search_bytes in msg:
                indices.append(i)
        while len(_search_cache) >= _SEARCH_CACHE_MAX and _search_cache_order:
            old_key = _search_cache_order.pop(0)
            _search_cache.pop(old_key, None)
        _search_cache[key] = indices
        _search_cache_order.append(key)
    else:
        _search_cache_order.remove(key)
        _search_cache_order.append(key)
    return _search_cache[key]


def _row_to_dict(log, index):
    line = log.get_line(index)
    ts = line[0]
    time_str = time_args(ts)[2:]  # absolute time MM:SS.ns
    level = line[3]
    level_name = level.name if isinstance(level, DebugLevel) else str(level)
    return {
        "time": time_str,
        "pid": line[1],
        "thread": "0x%07x" % line[2],
        "level": level_name,
        "category": line[4] or "",
        "filename": line[5] or "",
        "line": line[6],
        "function": line[7] or "",
        "object": line[8] or "",
        "message": line[9] if isinstance(line[9], str) else (line[9].decode("utf8", errors="replace") if line[9] else ""),
    }


def get_log(path, project_root, log_files_dir):
    path = norm_path(path, project_root, log_files_dir) if path and not os.path.isabs(path) else path
    if not path or not os.path.isfile(path):
        return None
    return _log_cache.get(path)


def _count_distinct_objects(log, indices):
    seen = set()
    for i in indices:
        obj = log._object_names_list[log._object_ids[i]]
        if obj:
            seen.add(obj)
    return len(seen)


def get_lines(path, project_root, log_files_dir, limit=500,
              level=None, category=None, thread=None, object_name=None, function=None, filename=None, search=None,
              time_start=None, time_end=None):
    path = norm_path(path, project_root, log_files_dir) if path and not os.path.isabs(path) else path
    log = _log_cache.get(path)
    if not log:
        return {"ok": False, "error": "Log not loaded"}
    limit = max(1, min(2000, limit))
    filtered = _get_filtered_indices(path, log, level, category, thread, object_name, function, filename, search, time_start, time_end)
    filtered_list = list(filtered) if not isinstance(filtered, list) else filtered
    total_matching = len(filtered_list)
    if total_matching > MAX_MATCHING_TO_RETURN_ROWS:
        object_count = _count_distinct_objects(log, filtered_list)
        msg = (
            f"total_matching ({total_matching}) exceeds maximum ({MAX_MATCHING_TO_RETURN_ROWS}). "
            "Use log_summary with the same filters to see counts; narrow filters (time range, level, category, object_name, search) and try again."
        )
        if object_count > MAX_OBJECTS_SUGGEST_NARROW:
            msg += f" There are {object_count} distinct objects in this range; narrow by object_name or search to reduce."
        return {
            "ok": True,
            "total_matching": total_matching,
            "object_count": object_count,
            "returned": 0,
            "rows": [],
            "message": msg,
        }
    indices = filtered_list[:limit]
    rows = [_row_to_dict(log, i) for i in indices]
    return {"ok": True, "rows": rows, "total_matching": total_matching, "returned": len(rows)}


def get_summary(path, project_root, log_files_dir,
                level=None, category=None, thread=None, object_name=None, function=None, filename=None, search=None,
                time_start=None, time_end=None):
    """Return counts only (no raw lines) for the filtered set. time_start/time_end: integer milliseconds from log start (no fractions)."""
    path = norm_path(path, project_root, log_files_dir) if path and not os.path.isabs(path) else path
    log = _log_cache.get(path)
    if not log:
        return {"ok": False, "error": "Log not loaded"}
    filtered = _get_filtered_indices(path, log, level, category, thread, object_name, function, filename, search, time_start, time_end)
    indices = list(filtered) if not isinstance(filtered, list) else filtered
    count_by_level = {}
    count_by_category = {}
    count_by_object = {}
    for i in indices:
        lv = log.levels[i]
        lv_name = lv.name if hasattr(lv, "name") else str(lv)
        count_by_level[lv_name] = count_by_level.get(lv_name, 0) + 1
        cat = log._category_names[log._category_ids[i]]
        count_by_category[cat] = count_by_category.get(cat, 0) + 1
        obj = log._object_names_list[log._object_ids[i]]
        if obj:
            count_by_object[obj] = count_by_object.get(obj, 0) + 1
    return {
        "ok": True,
        "total_matching": len(indices),
        "count_by_level": count_by_level,
        "count_by_category": count_by_category,
        "count_by_object": count_by_object,
    }


def get_object_summary(path, project_root, log_files_dir, category, time_start, time_end):
    """Per-level count of distinct objects and full object list in the given category and time range. category, time_start, time_end required. Time: integer milliseconds from log start (no fractions)."""
    path = norm_path(path, project_root, log_files_dir) if path and not os.path.isabs(path) else path
    log = _log_cache.get(path)
    if not log:
        return {"ok": False, "error": "Log not loaded"}
    filtered = _get_filtered_indices(path, log, level=None, category=category, thread=None, obj=None, function=None, filename=None, search=None, time_start=time_start, time_end=time_end)
    indices = list(filtered) if not isinstance(filtered, list) else filtered
    # Per level: set of distinct object names
    objects_by_level = {}
    all_objects = set()
    for i in indices:
        lv = log.levels[i]
        lv_name = lv.name if hasattr(lv, "name") else str(lv)
        obj = log._object_names_list[log._object_ids[i]]
        if obj:
            all_objects.add(obj)
            if lv_name not in objects_by_level:
                objects_by_level[lv_name] = set()
            objects_by_level[lv_name].add(obj)
    count_by_level = {k: len(v) for k, v in objects_by_level.items()}
    return {
        "ok": True,
        "total_matching": len(indices),
        "count_by_level": count_by_level,
        "object_names": sorted(all_objects),
    }


