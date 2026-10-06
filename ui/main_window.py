# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 五个页面 + 全局状态。"""
from __future__ import annotations

import os
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from core.config import APP_NAME, AppConfig, load_config, save_config
from core.model import ScanResult
from ui import theme as theme_mod
from ui.batch_page import BatchPage
from ui.home_page import HomePage
from ui.result_page import ResultPage
from ui.scan_page import ScanPage
from ui.settings_page import SettingsPage


class Store:
    """全局共享状态。"""

    def __init__(self):
        self.cfg: AppConfig = load_config()
        self.result: ScanResult | None = None
        self.selection: set = set()


class MainWindow(QMainWindow):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.setWindowTitle(f"{APP_NAME} - 只读扫描 · 受控清理")
        self.resize(1280, 820)
        self.setMinimumSize(1040, 700)
        self._build()
        self._apply_theme()
        self._first_run_notice()

    # ---------- 界面 ----------
    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边导航
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(168)
        side.setStyleSheet(
            "QFrame#sidebar{background:#FFFFFF;border-right:1px solid #E4E8EE;}"
            "QPushButton{border:none;text-align:left;padding:12px 16px;border-radius:10px;"
            "background:transparent;color:#424A53;font-size:14px;margin:2px 8px;}"
            "QPushButton:hover{background:#F0F6FF;color:#2D7FF9;}"
            "QPushButton#navActive{background:#E3EEFF;color:#1B5FD9;font-weight:700;}")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 20, 0, 12)
        logo = QLabel("🗂️\n磁盘文件\n检视工具")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size:15px;font-weight:700;color:#1B5FD9;line-height:1.4;")
        sl.addWidget(logo)
        sl.addSpacing(16)

        self.navs = []
        pages = QStackedWidget()
        self.home = HomePage()
        self.scan = ScanPage()
        self.result = ResultPage(self.store)
        self.batch = BatchPage(self.store)
        self.settings = SettingsPage(self.store)
        for name in ["🏠 首页", "⚡ 扫描进度", "📋 结果预览", "🛠️ 批量操作", "⚙️ 设置"]:
            b = QPushButton(name)
            b.clicked.connect(lambda _, n=name: self._nav_to(n))
            self.navs.append(b)
            sl.addWidget(b)
        sl.addStretch(1)
        ver = QLabel("v1.0 · 本工具只读扫描，绝不擅自删除")
        ver.setWordWrap(True)
        ver.setStyleSheet("color:#8B949E;font-size:11px;padding:8px 16px;")
        sl.addWidget(ver)
        root.addWidget(side)
        root.addWidget(pages, 1)

        for p in [self.home, self.scan, self.result, self.batch, self.settings]:
            pages.addWidget(p)
        self.pages = pages

        # 信号
        self.home.start_scan.connect(self.start_scan)
        self.home.open_settings.connect(lambda: self._nav_to("⚙️ 设置"))
        self.home.show_help.connect(self.show_help)
        self.home.create_shortcut.connect(self.settings._create_shortcut)
        self.home.open_report.connect(self._open_last_report)
        self.scan.finished.connect(self._on_scan_finished)
        self.result.report_ready.connect(self._open_report_path)
        self.settings.settings_saved.connect(lambda: self._apply_theme())
        self.settings.theme_changed.connect(lambda t: self._apply_theme())

        self.setCentralWidget(central)
        self._nav_to("🏠 首页")

    def _nav_to(self, name: str) -> None:
        idx = {"🏠 首页": 0, "⚡ 扫描进度": 1, "📋 结果预览": 2, "🛠️ 批量操作": 3, "⚙️ 设置": 4}.get(name, 0)
        self.pages.setCurrentIndex(idx)
        for i, b in enumerate(self.navs):
            b.setObjectName("navActive" if i == idx else "")
            b.style().unpolish(b)
            b.style().polish(b)

    # ---------- 主题 ----------
    def _apply_theme(self) -> None:
        qss = theme_mod.get_qss(self.store.cfg.theme)
        self.setStyleSheet(qss)
        dark = self.store.cfg.theme == "dark"
        side_bg = "#1D232C" if dark else "#FFFFFF"
        side_line = "#2A323D" if dark else "#E4E8EE"
        nav_base = "#C9D3DE" if dark else "#424A53"
        nav_hover_bg = "#1D2836" if dark else "#F0F6FF"
        nav_hover_c = "#6FB1FF" if dark else "#2D7FF9"
        nav_active_bg = "#1D3A5F" if dark else "#E3EEFF"
        nav_active_c = "#6FB1FF" if dark else "#1B5FD9"
        self.navs[0].parent().setStyleSheet(
            f"QFrame#sidebar{{background:{side_bg};border-right:1px solid {side_line};}}"
            f"QPushButton{{border:none;text-align:left;padding:12px 16px;border-radius:10px;"
            f"background:transparent;color:{nav_base};font-size:14px;margin:2px 8px;}}"
            f"QPushButton:hover{{background:{nav_hover_bg};color:{nav_hover_c};}}"
            f"QPushButton#navActive{{background:{nav_active_bg};color:{nav_active_c};font-weight:700;}}")
        self.home.refresh_drives()

    # ---------- 扫描流程 ----------
    def start_scan(self, mode: str) -> None:
        from core.occupancy import disk_usage
        roots = []
        for d in ("C:\\", "D:\\"):
            if disk_usage(d):
                roots.append(d)
        if not roots:
            QMessageBox.warning(self, "无法扫描", "未检测到可读取的 C/D 盘。")
            return
        self.store.cfg.last_scan_mode = mode
        save_config(self.store.cfg)
        self.scan.start(roots, self.store.cfg, mode)
        self._nav_to("⚡ 扫描进度")

    def _on_scan_finished(self, result: ScanResult) -> None:
        try:
            self.store.result = result
            if result.stats.get("error"):
                QMessageBox.critical(self, "扫描失败", f"扫描过程中发生错误：\n{result.stats['error']}")
                self._nav_to("🏠 首页")
                return
            # build_index 已在扫描线程完成，这里只做界面加载
            self.result.load_result(result)
            self.batch.refresh()
            self._nav_to("📋 结果预览")
            if self.store.cfg.auto_open_report:
                self.result._export_html()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "处理扫描结果出错", f"{e}\n\n详细错误已记录到日志。")

    def closeEvent(self, event) -> None:
        """关闭窗口时先停止并等待后台线程，避免 'QThread destroyed while running' 崩溃。"""
        try:
            w = self.scan._worker
            if w and w.isRunning():
                w.stop_ev.set()
                w.wait(10000)
            self.result.wait_export(10000)
        except Exception:
            pass
        event.accept()

    def _open_report_path(self, path: str) -> None:
        if path and os.path.exists(path):
            from pathlib import Path
            webbrowser.open(Path(path).as_uri())
        else:
            QMessageBox.information(self, "提示", "还没有可打开的报告，请先完成一次扫描。")

    def _open_last_report(self) -> None:
        p = self.result._last_report
        if not p or not os.path.exists(p):
            QMessageBox.information(self, "提示", "还没有可打开的报告，请先完成一次扫描并导出报告。")
            return
        self._open_report_path(p)

    # ---------- 帮助 ----------
    def show_help(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("帮助说明")
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        txt = QLabel(
            "<b>磁盘文件检视工具 · 帮助</b><br><br>"
            "<b>1. 我该点什么？</b><br>"
            "首页点击「极速扫描」即可快速看到能清理的东西；想要最全的报告点「深度全盘扫描」。<br><br>"
            "<b>2. 哪些文件可以放心删除？</b><br>"
            "绿色「低危」的临时/缓存文件、卸载残留可以删除，不影响系统与软件。<br><br>"
            "<b>3. 哪些文件千万别动？</b><br>"
            "红色「高危」的系统核心文件已被自动锁定（🔒），勾选框是灰色的，你无法选中它们。<br><br>"
            "<b>4. 删除安全吗？</b><br>"
            "推荐使用「移入回收站」——删错了可以去系统回收站恢复。"
            "「彻底删除」会先移入本工具的安全回收箱，在操作历史里也能还原。<br><br>"
            "<b>5. 怎么清理大文件？</b><br>"
            "在结果页搜索/筛选「仅大型文件」，勾选后用「迁移」或「备份+删除」处理。<br><br>"
            "<b>6. 报告怎么看？</b><br>"
            "扫描完成后会自动生成 HTML 报告，双击文件夹展开、点表头排序、勾选后点「导出勾选清单」，"
            "再到本工具「批量操作 → 导入勾选清单」执行。<br><br>"
            "<b>7. 隐私安全</b><br>"
            "全程离线，不联网、不上传任何文件信息。")
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.TextFormat.RichText)
        scroll = QLabel("")
        lay.addWidget(txt)
        btn = QPushButton("关闭")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    # ---------- 首次启动 ----------
    def _first_run_notice(self) -> None:
        flag = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "DiskInspector", "first_run.v1")
        if os.path.exists(flag):
            return
        try:
            os.makedirs(os.path.dirname(flag), exist_ok=True)
            open(flag, "w").close()
        except Exception:
            pass
        QMessageBox.information(
            self, "欢迎使用 · 安全承诺",
            "欢迎使用磁盘文件检视工具！\n\n"
            "🔒 本工具【不会自动清理任何文件】：\n"
            "· 所有删除 / 备份 / 迁移操作，都必须由你手动勾选并二次确认；\n"
            "· 系统高危文件已锁定，永远无法勾选；\n"
            "· 推荐使用「移入回收站」，删错了可恢复；\n"
            "· 全部操作都会写入本地日志，可随时查看。\n\n"
            "点击「确定」开始吧！")
