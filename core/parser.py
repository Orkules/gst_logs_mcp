# -*- coding: utf-8 -*-
# Adapted from GStreamer Debug Viewer Data module (GstDebugViewer)
# Original Copyright (C) 2007 René Stadler

import os
import re
import sys
import math

SECOND = 1000000000


def time_args(ts):
    secs = ts // SECOND
    return "%i:%02i:%02i.%09i" % (secs // 60 ** 2, secs // 60 % 60, secs % 60, ts % SECOND)


def time_diff_args(time_diff):
    sign = "+" if time_diff >= 0 else "-"
    secs = abs(time_diff) // SECOND
    return "%s%02i:%02i.%09i" % (sign, secs // 60, secs % 60, abs(time_diff) % SECOND)


def parse_time(st):
    """Parse time string to nanoseconds. Accepts H:MM:SS or H:MM:SS.frac (e.g. 0:00:10 or 0:00:10.123456789)."""
    st = str(st).strip()
    h, m, s = st.split(":")
    if "." in s:
        secs, subsecs = s.split(".", 1)
        subsecs = (subsecs + "000000000")[:9]  # pad to nanosec
        subsec_ns = int(subsecs)
    else:
        secs = s
        subsec_ns = 0
    return int((int(h) * 60 ** 2 + int(m) * 60) * SECOND) + int(secs) * SECOND + subsec_ns


_TIME_RE = re.compile(r"^(\d+:\d\d:\d\d\.\d+)")


class DebugLevel(int):
    __names = ["NONE", "ERROR", "WARN", "FIXME", "INFO", "DEBUG", "LOG", "TRACE", "MEMDUMP"]
    __instances = {}

    def __new__(cls, level):
        try:
            level_int = int(level)
        except (ValueError, TypeError):
            try:
                level_int = cls.__names.index(level.upper())
            except ValueError:
                raise ValueError("no debug level named %r" % (level,))
        if level_int in cls.__instances:
            return cls.__instances[level_int]
        new_instance = int.__new__(cls, level_int)
        new_instance.name = cls.__names[level_int]
        cls.__instances[level_int] = new_instance
        return new_instance

    def __repr__(self):
        return "<%s %s (%i)>" % (type(self).__name__, self.__names[self], self)


debug_level_none = DebugLevel("NONE")
debug_level_error = DebugLevel("ERROR")
debug_level_warning = DebugLevel("WARN")
debug_level_info = DebugLevel("INFO")
debug_level_debug = DebugLevel("DEBUG")
debug_level_log = DebugLevel("LOG")
debug_level_fixme = DebugLevel("FIXME")
debug_level_trace = DebugLevel("TRACE")
debug_level_memdump = DebugLevel("MEMDUMP")
LEVEL_BY_LETTER = {"T": debug_level_trace, "F": debug_level_fixme, "L": debug_level_log,
                   "D": debug_level_debug, "I": debug_level_info, "W": debug_level_warning,
                   "E": debug_level_error, " ": debug_level_none, "M": debug_level_memdump}

_escape = re.compile(rb"\x1b\[[0-9;]*m")


def strip_escape(s):
    while b"\x1b" in s:
        s = _escape.sub(b"", s)
    return s


def _log_line_regex():
    LEVEL = r"([A-Z]+)\s*"
    THREAD = r"(0x[0-9a-f]+)\s+"
    TIME = r"(\d+:\d\d:\d\d\.\d+)\s+"
    CATEGORY = r"([A-Za-z0-9_-]+)\s+"
    PID = r"(\d+)\s*"
    FILENAME = r"([^:]*):"
    LINE = r"(\d+):"
    FUNCTION = r"(~?[A-Za-z0-9_\s\*,\(\)]*):"
    OBJECT = r"(?:<([^>]+)>)?"
    MESSAGE = r"(.+)"
    ANSI = r"(?:\x1b\[[0-9;]*m\s*)*\s*"
    expressions = [TIME, ANSI, PID, ANSI, THREAD, ANSI, LEVEL, ANSI,
                   CATEGORY, FILENAME, LINE, FUNCTION, ANSI, OBJECT, ANSI, MESSAGE]
    return re.compile("".join(expressions))


_LINE_REGEX = _log_line_regex()


class LogLine(list):
    @classmethod
    def parse_full(cls, line_bytes):
        s = line_bytes.decode("utf8", errors="replace")
        match = _LINE_REGEX.match(s)
        if match is None:
            return cls([0, 0, 0, 0, "", "", 0, "", "", 0])
        line = cls(match.groups())
        line[0] = parse_time(line[0])
        line[1] = int(line[1])
        line[2] = int(line[2], 16)
        line[3] = 0
        line[6] = int(line[6])
        line[9] = match.start(10)
        for col_id in (4, 5, 7, 8):
            line[col_id] = sys.intern(line[col_id] or "")
        return line


_OBJECT_NAME_DELIM_RE = re.compile(r"[\\:@/]")
_OBJECT_ANGLE_BRACKET_RE = re.compile(r"<([^>]+)>")


def _normalize_object_name(obj):
    if not obj:
        return None
    match = _OBJECT_NAME_DELIM_RE.search(obj)
    idx = match.start() if match else len(obj)
    name = obj[:idx].strip()
    return name if name else None


def _find_insert_pos(fileobj, offsets, time_len, insert_time_str):
    tell, seek, read = fileobj.tell, fileobj.seek, fileobj.read
    lo, hi = 0, len(offsets)
    enc = insert_time_str.encode("utf8")
    while lo < hi:
        mid = int(math.floor(lo * 0.1 + hi * 0.9))
        seek(offsets[mid])
        mid_str = read(time_len)
        if enc < mid_str:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _parse_filter_fields(line_str):
    try:
        parsed = LogLine.parse_full(line_str.encode("utf-8", errors="replace"))
    except Exception:
        return None
    cat = (parsed[4] or "").strip()
    thread_val = parsed[2]
    obj_raw = parsed[8] or ""
    if not (obj_raw or "").strip():
        m = _OBJECT_ANGLE_BRACKET_RE.search(line_str)
        obj_raw = m.group(1) if m else ""
    obj_norm = (_normalize_object_name(obj_raw) or "").strip()
    func = (parsed[7] or "").strip()
    fname = (parsed[5] or "").strip()
    return cat, thread_val, obj_norm, func, fname


def build_line_cache(fileobj, object_names=None):
    offsets = []
    levels = []
    category_ids = []
    threads = []
    object_ids = []
    function_ids = []
    filename_ids = []
    category_to_id = {}
    category_names = []
    object_to_id = {}
    object_names_list = []
    function_to_id = {}
    function_names = []
    filename_to_id = {}
    filename_names = []
    if object_names is None:
        object_names = set()
    timestamps = []
    time_len = len(time_args(0))
    ANSI = r"(?:\x1b\[[0-9;]*m)?"
    ANSI_PATTERN = r"\d:\d\d:\d\d\.\d+ " + ANSI + r" *\d+" + ANSI + r" +0x[0-9a-f]+ +" + ANSI + r"([TFLDIEWM ])"
    rexp_bare = re.compile(ANSI_PATTERN.replace(ANSI, ""))
    rexp_ansi = re.compile(ANSI_PATTERN)
    rexp = rexp_bare
    readline = fileobj.readline
    tell = fileobj.tell
    seek = fileobj.seek
    read = fileobj.read
    last_line = ""
    fileobj.seek(0)

    def add_line(offset, line, lvl):
        cat, thread_val, obj_norm, func, fname = _parse_filter_fields(line) or ("", 0, "", "", "")
        cat_id = category_to_id.get(cat, len(category_names))
        if cat_id == len(category_names):
            category_to_id[cat] = cat_id
            category_names.append(cat)
        obj_id = object_to_id.get(obj_norm, len(object_names_list))
        if obj_id == len(object_names_list):
            object_to_id[obj_norm] = obj_id
            object_names_list.append(obj_norm)
            if obj_norm:
                object_names.add(obj_norm)
        func_id = function_to_id.get(func, len(function_names))
        if func_id == len(function_names):
            function_to_id[func] = func_id
            function_names.append(func)
        fname_id = filename_to_id.get(fname, len(filename_names))
        if fname_id == len(filename_names):
            filename_to_id[fname] = fname_id
            filename_names.append(fname)
        return (cat_id, thread_val, obj_id, func_id, fname_id)

    while True:
        offset = tell()
        line = readline().decode("utf-8", errors="replace")
        if not line:
            break
        match = rexp.match(line)
        if match is None:
            if rexp is rexp_ansi or "\x1b" not in line:
                continue
            match = rexp_ansi.match(line)
            if match is None:
                continue
            rexp = rexp_ansi
        lvl = LEVEL_BY_LETTER.get(match.group(1), debug_level_none)
        filter_fields = add_line(offset, line, lvl)
        cat_id, thread_val, obj_id, func_id, fname_id = filter_fields
        time_match = _TIME_RE.match(line)
        ts = parse_time(time_match.group(1)) if time_match else 0
        if line >= last_line:
            levels.append(lvl)
            offsets.append(offset)
            timestamps.append(ts)
            category_ids.append(cat_id)
            threads.append(thread_val)
            object_ids.append(obj_id)
            function_ids.append(func_id)
            filename_ids.append(fname_id)
            last_line = line
        else:
            pos = _find_insert_pos(fileobj, offsets, time_len, line[:time_len])
            levels.insert(pos, lvl)
            offsets.insert(pos, offset)
            timestamps.insert(pos, ts)
            category_ids.insert(pos, cat_id)
            threads.insert(pos, thread_val)
            object_ids.insert(pos, obj_id)
            function_ids.insert(pos, func_id)
            filename_ids.insert(pos, fname_id)
            seek(offset)
            readline()
    return (
        offsets,
        levels,
        timestamps,
        category_ids,
        category_names,
        threads,
        object_ids,
        object_names_list,
        function_ids,
        function_names,
        filename_ids,
        filename_names,
    )


class LogFile:
    def __init__(self, filepath):
        self.path = os.path.normpath(os.path.abspath(filepath))
        self._f = open(self.path, "rb")
        try:
            import mmap
            self._mmap = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        except Exception:
            self._mmap = None
        self._object_names = set()
        result = build_line_cache(self._mmap or self._f, self._object_names)
        (
            self.offsets,
            self.levels,
            self._timestamps,
            self._category_ids,
            self._category_names,
            self._threads,
            self._object_ids,
            self._object_names_list,
            self._function_ids,
            self._function_names,
            self._filename_ids,
            self._filename_names,
        ) = result
        self._fileobj = self._mmap or self._f
        self._category_to_id = {c: i for i, c in enumerate(self._category_names)}
        self._object_to_id = {o: i for i, o in enumerate(self._object_names_list)}
        self._function_to_id = {f: i for i, f in enumerate(self._function_names)}
        self._filename_to_id = {f: i for i, f in enumerate(self._filename_names)}

    @property
    def object_names(self):
        return self._object_names

    @property
    def category_names(self):
        return sorted(set(self._category_names))

    @property
    def level_names(self):
        return sorted(set(lv.name if hasattr(lv, "name") else str(lv) for lv in self.levels))

    @property
    def time_span(self):
        """(min_ts_ns, max_ts_ns) for the log."""
        if not self._timestamps:
            return (0, 0)
        return (self._timestamps[0], self._timestamps[-1])

    def get_filtered_indices(self, level=None, category=None, thread=None, object_name=None, function=None, filename=None, time_min=None, time_max=None):
        n = len(self.offsets)
        level_val = None
        if level:
            try:
                level_val = DebugLevel(level)
            except ValueError:
                pass
        cat_id = self._category_to_id.get(category) if (category is not None and category != "") else None
        obj_id = self._object_to_id.get(object_name) if (object_name is not None and object_name != "") else None
        func_id = self._function_to_id.get(function) if (function is not None and function != "") else None
        fname_id = self._filename_to_id.get(filename) if (filename is not None and filename != "") else None
        if (category and cat_id is None) or (object_name and obj_id is None) or (function and func_id is None) or (filename and fname_id is None):
            return []
        has_any = (level_val is not None or cat_id is not None or thread is not None or obj_id is not None or
                   func_id is not None or fname_id is not None or time_min is not None or time_max is not None)
        if not has_any:
            return range(n)
        indices = []
        for i in range(n):
            if level_val is not None and self.levels[i] != level_val:
                continue
            if cat_id is not None and self._category_ids[i] != cat_id:
                continue
            if thread is not None and self._threads[i] != thread:
                continue
            if obj_id is not None and self._object_ids[i] != obj_id:
                continue
            if func_id is not None and self._function_ids[i] != func_id:
                continue
            if fname_id is not None and self._filename_ids[i] != fname_id:
                continue
            if time_min is not None and self._timestamps[i] < time_min:
                continue
            if time_max is not None and self._timestamps[i] > time_max:
                continue
            indices.append(i)
        return indices

    def get_line(self, index):
        self._fileobj.seek(self.offsets[index])
        raw = self._fileobj.readline()
        line = LogLine.parse_full(raw)
        msg_char_start = line[9]
        s = raw.decode("utf8", errors="replace")
        if not (line[8] or "").strip():
            m = _OBJECT_ANGLE_BRACKET_RE.search(s)
            if m:
                line[8] = m.group(1)
        byte_start = len(s[:msg_char_start].encode("utf8"))
        line[9] = raw[byte_start:].decode("utf8", errors="replace")
        line[3] = self.levels[index]
        return line

    def __len__(self):
        return len(self.offsets)

    def close(self):
        if self._mmap:
            self._mmap.close()
        self._f.close()
