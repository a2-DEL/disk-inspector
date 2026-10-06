# -*- coding: utf-8 -*-
"""稳定性专项：5 万文件深度扫描 GUI 全链路 + 收尾异常注入验证。

- 正常模式：ScanWorker(深度) -> build_index(线程内) -> 结果页 -> ReportWorker 导出 -> 进程存活
- 注入模式：STABILITY_INJECT=1 时扫描完成回调人为抛异常，验证 excepthook 兜底、进程不退出
"""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["APPDATA"] = os.path.join(os.getcwd(), "_st_appdata")
os.makedirs(os.path.join(os.environ["APPDATA"], "DiskInspector"), exist_ok=True)
open(os.path.join(os.environ["APPDATA"], "DiskInspector", "first_run.v1"), "w").close()

INJECT = os.environ.get("STABILITY_INJECT") == "1"

sys.path.insert(0, os.getcwd())
import main as m
m._install_excepthook()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)

from core.config import AppConfig
from core.model import ScanResult
from ui.scan_page import ScanWorker
from ui.result_page import ResultPage
from ui.main_window import Store

BASE = os.path.join(os.getcwd(), "_st_fix")
if os.path.exists(BASE):
    import shutil
    shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(BASE)

t0 = time.time()
for i in range(500):
    d = os.path.join(BASE, f"dir{i:03d}")
    os.makedirs(d)
    for j in range(100):
        with open(os.path.join(d, f"f{j:03d}.dat"), "wb") as f:
            f.write(b"\0" * 1024)
print(f"数据就绪 {time.time()-t0:.1f}s（500 目录 × 100 文件 = 5 万文件）")

cfg = AppConfig()
cfg.auto_open_report = False
cfg.large_threshold_mb = 1
store = Store()
store.cfg = cfg
rp = ResultPage(store)

state = {"scan_done": False, "export_ok": False, "export_path": "", "inject_ok": False}


def on_scan_done(res):
    assert isinstance(res, ScanResult)
    assert res.stats.get("error") is None, f"扫描出错: {res.stats['error']}"
    print(f"深度扫描完成：files={res.stats['files']} dirs={res.stats['dirs']} "
          f"索引={len(res.children)} 子项")
    store.result = res
    # 异常注入点：模拟收尾阶段槽内出错（修复前此处会 abort 静默退出）
    if INJECT:
        raise RuntimeError("STABILITY_INJECT: 模拟扫描收尾槽内异常")
    rp.load_result(res)
    rp._export_html()
    state["scan_done"] = True


def on_export_done_ok(path):
    state["export_ok"] = True
    state["export_path"] = path


def poll():
    app.processEvents()
    if rp._last_report:
        state["export_ok"] = True
        state["export_path"] = rp._last_report
        app.quit()
        return
    QTimer.singleShot(50, poll)


worker = ScanWorker([BASE], cfg, "deep")
worker.done.connect(on_scan_done)
worker.start()
QTimer.singleShot(50, poll)

rc = app.exec()
print("app.exec 返回:", rc, "=> 事件循环正常结束")

if INJECT:
    # 注入模式：验证 excepthook 已拦截、进程存活
    log = os.path.join(os.environ["APPDATA"], "DiskInspector", "error.log")
    data = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
    assert "STABILITY_INJECT" in data, "异常未被 excepthook 记录"
    print("✅ 注入模式：收尾槽异常被 excepthook 拦截，进程未退出，error.log 已记录")
else:
    html = open(state["export_path"], encoding="utf-8").read()
    import re
    me = re.search(r"DATA\.entries = (\[.*?\]);", html, re.S)
    entries = len(__import__("json").loads(me.group(1)))
    print(f"✅ 正常模式：HTML 导出 {os.path.getsize(state['export_path'])/1048576:.1f} MB，"
          f"entries={entries}，全链路稳定，进程未退出")

import shutil
shutil.rmtree(BASE, ignore_errors=True)
print("STABILITY_OK")
