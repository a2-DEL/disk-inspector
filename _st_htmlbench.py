import os, sys, time
sys.path.insert(0, os.getcwd())
from core.config import AppConfig
from core.scanner import scan
from core.report import generate_html
BASE = os.path.join(os.getcwd(), "_st_fix")
t0 = time.time()
res = scan([BASE], AppConfig(), "deep")
t1 = time.time()
res.build_index()
t2 = time.time()
out = os.path.join(os.getcwd(), "_st_report.html")
t3 = time.time()
generate_html(res, AppConfig(), out)
t4 = time.time()
print("scan=%.1fs build_index=%.2fs html=%.1fs html_size=%.1fMB files=%d" % (t1-t0, t2-t1, t4-t3, os.path.getsize(out)/1048576, res.stats["files"]))
