# -*- coding: utf-8 -*-
"""磁盘文件检视工具 - 程序入口。

启动流程：检查管理员权限 → 不足则请求提权 → 显示主界面。
"""
from __future__ import annotations

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def _install_excepthook() -> None:
    """安装全局异常兜底。

    PyQt6 中槽函数若抛出未捕获异常会直接 abort() 导致程序静默退出
    （深度扫描收尾等场景的内存异常/逻辑异常都可能触发）。
    这里将异常写入本地日志并弹窗提示，保证程序不崩溃、可继续使用。
    """
    import traceback
    import datetime

    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log_dir = os.path.join(os.environ.get("APPDATA", "."), "DiskInspector")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "error.log"), "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n{text}\n")
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, "程序遇到错误",
                    "程序遇到一个未预期的错误，已记录到日志，程序将继续运行。\n\n"
                    f"{exc_type.__name__}: {exc_value}\n\n"
                    f"日志位置：{os.path.join(os.environ.get('APPDATA', '.'), 'DiskInspector', 'error.log')}")
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    _install_excepthook()
    # 打包产物自检：DISK_INSPECTOR_SELFTEST=1 时离屏跑通核心链路（无窗口、无需提权）
    if os.environ.get("DISK_INSPECTOR_SELFTEST") == "1":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            import tempfile
            from PyQt6.QtWidgets import QApplication
            _app = QApplication(sys.argv)
            from core.classifier import Classifier
            from core.config import AppConfig
            from core.model import ScanResult
            from core.report import generate_html
            c = Classifier()
            assert c.rules.get("whitelist"), "rules 未加载"
            r = ScanResult(roots=["C:\\"], entries=[])
            out = os.path.join(tempfile.gettempdir(), "disk_inspector_selftest.html")
            generate_html(r, AppConfig(), out)
            assert os.path.exists(out) and os.path.getsize(out) > 1000
            print("SELFTEST_OK")
            return 0
        except Exception as e:
            print("SELFTEST_FAIL:", e)
            return 2

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("磁盘文件检视工具")
    app.setFont(QFont("Microsoft YaHei", 10))

    # 管理员权限：扫描系统目录与执行文件操作需要
    from core.admin import is_admin, relaunch_as_admin
    if not is_admin():
        ok = relaunch_as_admin()
        if not ok:
            QMessageBox.warning(
                None, "需要管理员权限",
                "本工具需要【以管理员身份运行】才能完整扫描系统目录并执行文件操作。\n\n"
                "请在系统弹出的 UAC 提示中选择「是」，或在右键菜单中勾选「以管理员身份运行」。")
            return 1
        return 0  # 新进程已启动，本进程退出

    from ui.main_window import MainWindow, Store
    win = MainWindow(Store())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
