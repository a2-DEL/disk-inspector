# -*- coding: utf-8 -*-
"""真实磁盘扫描基准：单次执行 一个盘 + 一种模式，输出 JSON 到 _bench_out/。"""
import ctypes
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import AppConfig
from core.scanner import scan
from core.report import generate_html


class MemSampler:
    def __init__(self):
        self.peak = 0
        self._stop = False
        self._t = None

    @staticmethod
    def _ws():
        try:
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = PMC()
            c.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            fn = psapi.GetProcessMemoryInfo
            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_size_t]
            fn.restype = ctypes.c_int
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            h = k32.GetCurrentProcess()
            if fn(h, ctypes.byref(c), c.cb):
                return c.WorkingSetSize
            return 0
        except Exception:
            return 0

    def _sample(self):
        while not self._stop:
            v = self._ws()
            if v > self.peak:
                self.peak = v
            time.sleep(0.1)

    def start(self):
        self._t = threading.Thread(target=self._sample, daemon=True)
        self._t.start()

    def stop(self):
        self._stop = True
        if self._t:
            self._t.join(1)


def main():
    root, mode = sys.argv[1], sys.argv[2]
    cfg = AppConfig()
    mem = MemSampler()
    mem.start()
    t0 = time.time()
    res = scan([root], cfg, mode)
    t1 = time.time()
    # HTML 生成计时（复用真实结果）
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"_bench_out/report_{mode}_{root.rstrip(':\\\\').rstrip('\\\\').replace('\\\\', '_')}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t2 = time.time()
    generate_html(res, cfg, out)
    t3 = time.time()
    mem.stop()
    s = res.stats
    data = {
        "root": root, "mode": mode,
        "scan_sec": round(t1 - t0, 2),
        "html_sec": round(t3 - t2, 2),
        "html_kb": round(os.path.getsize(out) / 1024, 1),
        "files": s.get("files", 0), "dirs": s.get("dirs", 0),
        "size_bytes": s.get("size", 0),
        "skipped": s.get("skipped", 0),
        "large": s.get("large", 0), "junk": s.get("junk", 0),
        "locked": s.get("locked", 0),
        "peak_mem_mb": round(mem.peak / (1024 * 1024), 1),
        "by_category": s.get("by_category", {}),
        "by_risk": s.get("by_risk", {}),
        "threshold_mb": cfg.large_threshold_mb,
    }
    os.makedirs("_bench_out", exist_ok=True)
    tag = f"{root.rstrip(chr(92))[0]}_{mode}"
    with open(f"_bench_out/{tag}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
