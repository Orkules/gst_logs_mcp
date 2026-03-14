import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.service import load_log, get_summary

root = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(root, "gst_log_files")
path = os.path.join(log_dir, "gst_debug.log")

r = load_log(path, root, log_dir)
print(r)

s = get_summary(path, root, log_dir, level="DEBUG", category="queue")
print(s)
