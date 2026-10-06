# -*- coding: utf-8 -*-
"""页面5：设置页面。"""
from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from core.config import AppConfig, appdata_dir, save_config
from core import logger
from ui.widgets import HelpTip, make_card


class SettingsPage(QWidget):
    settings_saved = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self, store, parent: QWidget = None):
        super().__init__(parent)
        self.store = store
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        cfg = self.store.cfg

        # 扫描设置
        g1 = QGroupBox("扫描设置")
        f1 = QFormLayout(g1)
        f1.setSpacing(10)
        th_row = QHBoxLayout()
        self.cb_th = QComboBox()
        self.cb_th.addItems(["50 MB", "100 MB", "500 MB", "1 GB"])
        self.cb_th.setCurrentIndex(1)
        self.sp_th = QSpinBox()
        self.sp_th.setRange(10, 102400)
        self.sp_th.setSuffix(" MB")
        self.sp_th.setValue(cfg.large_threshold_mb)
        th_row.addWidget(self.cb_th)
        th_row.addWidget(QLabel("或自定义："))
        th_row.addWidget(self.sp_th)
        th_row.addStretch(1)
        f1.addRow("大文件阈值", th_row)
        self.cb_hidden = QCheckBox("显示隐藏文件")
        self.cb_protected = QCheckBox("显示系统受保护文件（高危文件仅展示并锁定，无法勾选）")
        self.cb_occ = QCheckBox("扫描时检测文件占用状态（略慢，占用文件禁止操作）")
        self.cb_dup = QCheckBox("深度扫描时检测重复文件（按哈希比对，较慢）")
        self.cb_hidden.setChecked(cfg.show_hidden)
        self.cb_protected.setChecked(cfg.show_protected)
        self.cb_occ.setChecked(cfg.check_occupied)
        self.cb_dup.setChecked(cfg.find_duplicates)
        f1.addRow("", self.cb_hidden)
        f1.addRow("", self.cb_protected)
        f1.addRow("", self.cb_occ)
        f1.addRow("", self.cb_dup)
        lay.addWidget(g1)

        # 路径
        g2 = QGroupBox("存储路径")
        f2 = QFormLayout(g2)
        f2.setSpacing(10)
        self.ed_html = QLineEdit(cfg.html_dir_resolved)
        b1 = QPushButton("浏览")
        b1.clicked.connect(lambda: self._pick(self.ed_html, "选择 HTML 报告保存目录"))
        row1 = QHBoxLayout()
        row1.addWidget(self.ed_html)
        row1.addWidget(b1)
        f2.addRow("HTML 报告保存路径", row1)
        self.ed_bak = QLineEdit(cfg.backup_dir_resolved)
        b2 = QPushButton("浏览")
        b2.clicked.connect(lambda: self._pick(self.ed_bak, "选择备份默认目录"))
        row2 = QHBoxLayout()
        row2.addWidget(self.ed_bak)
        row2.addWidget(b2)
        f2.addRow("备份默认存储路径", row2)
        self.cb_auto = QCheckBox("扫描完成后自动生成并打开 HTML 报告")
        self.cb_auto.setChecked(cfg.auto_open_report)
        f2.addRow("", self.cb_auto)
        lay.addWidget(g2)

        # 外观与日志
        g3 = QGroupBox("外观 / 日志 / 快捷方式")
        f3 = QFormLayout(g3)
        f3.setSpacing(10)
        theme_row = QHBoxLayout()
        self.rb_light = QRadioButton("浅色")
        self.rb_dark = QRadioButton("深色")
        (self.rb_light if cfg.theme == "light" else self.rb_dark).setChecked(True)
        self.rb_light.toggled.connect(lambda on: on and self.theme_changed.emit("light"))
        self.rb_dark.toggled.connect(lambda on: on and self.theme_changed.emit("dark"))
        theme_row.addWidget(self.rb_light)
        theme_row.addWidget(self.rb_dark)
        theme_row.addStretch(1)
        f3.addRow("界面主题", theme_row)
        self.sp_log = QSpinBox()
        self.sp_log.setRange(1, 365)
        self.sp_log.setValue(cfg.log_keep_days)
        self.sp_log.setSuffix(" 天")
        log_row = QHBoxLayout()
        b_clean = QPushButton("立即清理过期日志")
        b_clean.clicked.connect(self._clean_logs)
        log_row.addWidget(self.sp_log)
        log_row.addWidget(b_clean)
        log_row.addStretch(1)
        f3.addRow("日志保留", log_row)
        sc_row = QHBoxLayout()
        b_sc = QPushButton("🖱️ 创建桌面快捷方式")
        b_rm = QPushButton("删除桌面快捷方式")
        b_sc.clicked.connect(self._create_shortcut)
        b_rm.clicked.connect(self._remove_shortcut)
        sc_row.addWidget(b_sc)
        sc_row.addWidget(b_rm)
        sc_row.addStretch(1)
        f3.addRow("快捷方式", sc_row)
        lay.addWidget(g3)

        # 高级
        g4 = QGroupBox("高级：扫描白名单（小白默认不建议修改）")
        f4 = QFormLayout(g4)
        f4.setSpacing(8)
        tip = HelpTip("白名单内的目录会被标记为系统高危文件，全部锁定不可勾选、禁止删除与迁移。\n每行一个目录，如：C:\\Windows\\System32")
        f4.addRow("说明", tip)
        self.ed_wl = QLineEdit()
        self.ed_wl.setPlaceholderText("额外白名单目录，每行一个（可选）")
        self.ed_wl.setText("\n".join(cfg.whitelist_extra))
        f4.addRow("白名单", self.ed_wl)
        lay.addWidget(g4)

        # 保存
        row = QHBoxLayout()
        b_save = QPushButton("💾 保存设置")
        b_save.setObjectName("primary")
        b_save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(b_save)
        lay.addLayout(row)
        lay.addStretch(1)

    def _pick(self, ed: QLineEdit, title: str) -> None:
        d = QFileDialog.getExistingDirectory(self, title, ed.text() or os.path.expanduser("~"))
        if d:
            ed.setText(d)

    def _clean_logs(self) -> None:
        n = logger.cleanup_logs(self.sp_log.value())
        QMessageBox.information(self, "完成", f"已清理 {n} 条过期日志。")

    def _save(self) -> None:
        cfg = self.store.cfg
        sel = self.cb_th.currentText()
        cfg.large_threshold_mb = {"50 MB": 50, "100 MB": 100, "500 MB": 500, "1 GB": 1024}.get(sel, self.sp_th.value())
        if sel not in ("50 MB", "100 MB", "500 MB", "1 GB"):
            cfg.large_threshold_mb = self.sp_th.value()
        cfg.show_hidden = self.cb_hidden.isChecked()
        cfg.show_protected = self.cb_protected.isChecked()
        cfg.check_occupied = self.cb_occ.isChecked()
        cfg.find_duplicates = self.cb_dup.isChecked()
        cfg.html_dir = self.ed_html.text().strip()
        cfg.backup_dir = self.ed_bak.text().strip()
        cfg.auto_open_report = self.cb_auto.isChecked()
        cfg.theme = "dark" if self.rb_dark.isChecked() else "light"
        cfg.log_keep_days = self.sp_log.value()
        cfg.whitelist_extra = [l.strip() for l in self.ed_wl.text().splitlines() if l.strip()]
        save_config(cfg)
        self.settings_saved.emit()
        QMessageBox.information(self, "已保存", "设置已保存，将在下次扫描时生效。")

    def _shortcut_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Desktop", "磁盘文件检视工具.lnk")

    def _target(self) -> str:
        import sys
        if getattr(sys, "frozen", False):
            return sys.executable
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))

    def _create_shortcut(self) -> None:
        target = self._target()
        lnk = self._shortcut_path()
        ps = (
            "$ws = New-Object -ComObject WScript.Shell;"
            f"$s = $ws.CreateShortcut('{lnk}');"
            f"$s.TargetPath = '{target}';"
            f"$s.WorkingDirectory = '{os.path.dirname(target)}';"
            f"$s.Description = '磁盘文件检视工具';"
            "$s.Save()"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           check=True, capture_output=True, timeout=30)
            QMessageBox.information(self, "完成", f"桌面快捷方式已创建：\n{lnk}")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"创建快捷方式失败：{e}")

    def _remove_shortcut(self) -> None:
        lnk = self._shortcut_path()
        try:
            if os.path.exists(lnk):
                os.remove(lnk)
                QMessageBox.information(self, "完成", "桌面快捷方式已删除。")
            else:
                QMessageBox.information(self, "提示", "未找到桌面快捷方式。")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"删除快捷方式失败：{e}")
