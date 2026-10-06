# -*- coding: utf-8 -*-
"""GUI 冒烟测试：离屏创建主窗口，加载扫描结果，模拟勾选与导出。"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from PyQt6.QtWidgets import QApplication

from core.config import AppConfig
from core.scanner import scan
from ui.main_window import MainWindow, Store


def main():
    # 预置首次运行标志，避免弹窗阻塞离屏测试
    import os as _os
    flag = _os.path.join(_os.environ["APPDATA"], "DiskInspector", "first_run.v1")
    _os.makedirs(_os.path.dirname(flag), exist_ok=True)
    open(flag, "w").close()

    app = QApplication(sys.argv)
    store = Store()
    store.cfg.large_threshold_mb = 10
    win = MainWindow(store)
    win.show()

    # 扫描夹具目录并载入结果页
    fix = os.path.join(BASE, "_testfix")
    res = scan([fix], store.cfg, "deep")
    res.build_index()
    store.result = res

    win.result.load_result(res)
    win.batch.refresh()

    # 模拟勾选：选中所有非锁定文件
    for e in res.entries:
        if not e.locked and not e.occupied:
            store.selection.add(e.path)
    win.result._refresh_table()
    win.result._update_stats()
    n = len(store.selection)
    assert n > 0, "勾选应为非空"
    print(f"GUI 勾选：{n} 项")

    # 导出 HTML（异步后台线程，需轮询等待完成）
    import time as _time
    win.result._export_html()
    for _ in range(400):
        app.processEvents()
        if win.result._last_report:
            break
        _time.sleep(0.05)
    last = win.result._last_report
    assert last and os.path.exists(last), "HTML 报告未生成"
    print(f"GUI 导出报告：{last}（{os.path.getsize(last) // 1024} KB）")

    # 切换到批量页并取预览
    win.batch._refresh_summary()
    print(f"批量页预览行数：{win.batch.preview.rowCount()}")

    # 校验嵌入 HTML 的数据可解析（流式结构：var DATA = {...}; DATA.entries = [...]）
    with open(last, "r", encoding="utf-8") as f:
        html = f.read()
    import re
    m = re.search(r"var DATA = (\{.*?\});\nDATA\.entries = \[", html, re.S)
    assert m, "未找到 DATA"
    import json
    data = json.loads(m.group(1))
    me = re.search(r"DATA\.entries = (\[.*?\]);", html, re.S)
    assert me, "未找到 DATA.entries"
    entries = json.loads(me.group(1))
    assert len(entries) == len(res.entries)
    print(f"HTML 嵌入 JSON 校验通过：{len(entries)} 条")

    # 主题切换
    store.cfg.theme = "dark"
    win._apply_theme()
    store.cfg.theme = "light"
    win._apply_theme()
    print("主题切换通过 ✓")

    # 离屏截图（结果页 + 首页）
    win.result_page_nav_check = None
    win.pages.setCurrentIndex(2)
    app.processEvents()
    win.grab().save(os.path.join(BASE, "test_gui_result.png"))
    win.pages.setCurrentIndex(0)
    app.processEvents()
    win.grab().save(os.path.join(BASE, "test_gui_home.png"))
    print("离屏截图已保存 ✓")

    print("\n✅ GUI 冒烟测试通过")


if __name__ == "__main__":
    main()
