# -*- coding: utf-8 -*-
"""页面1：首页欢迎页。"""
from __future__ import annotations

import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.config import APP_NAME
from ui.widgets import DriveUsage, HelpTip, make_card


class HomePage(QWidget):
    start_scan = pyqtSignal(str)      # "fast" / "deep"
    open_settings = pyqtSignal()
    show_help = pyqtSignal()
    create_shortcut = pyqtSignal()
    open_report = pyqtSignal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # 标题 + 安全提示
        title = QLabel(f"欢迎使用{APP_NAME}")
        title.setObjectName("h1")
        lay.addWidget(title)
        tip = QLabel(
            "🛡️ 本工具【只读扫描 + 人工确认】：不会自动删除任何文件。"
            "所有删除/备份/迁移操作，都必须由你手动勾选并二次确认；系统高危文件已锁定，永远无法勾选。")
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "background:#E8F1FE;color:#1B5FD9;border-radius:10px;padding:12px 14px;font-size:13px;")
        lay.addWidget(tip)

        # 盘符占用
        grid = QGridLayout()
        grid.setSpacing(14)
        self.drives = []
        for i, d in enumerate(["C:\\", "D:\\"]):
            w = DriveUsage(d)
            self.drives.append(w)
            grid.addWidget(w, 0, i)
        lay.addLayout(grid)

        # 两大扫描按钮
        btns = QHBoxLayout()
        btns.setSpacing(16)
        self.btn_fast = QPushButton("⚡ 极速扫描")
        self.btn_fast.setObjectName("bigPrimary")
        self.btn_fast.setToolTip("只扫描大文件、临时/缓存目录与卸载残留，跳过系统核心目录，速度快")
        self.btn_fast.setMinimumHeight(64)
        self.btn_deep = QPushButton("🔍 深度全盘扫描")
        self.btn_deep.setObjectName("big")
        self.btn_deep.setToolTip("遍历全部目录，完整采集每个文件的属性（更慢但更全）")
        self.btn_deep.setMinimumHeight(64)
        self.btn_fast.clicked.connect(lambda: self.start_scan.emit("fast"))
        self.btn_deep.clicked.connect(lambda: self.start_scan.emit("deep"))
        btns.addWidget(self.btn_fast, 3)
        btns.addWidget(self.btn_deep, 3)
        lay.addLayout(btns)

        # 说明行
        hint = QHBoxLayout()
        hint.addWidget(HelpTip(
            "极速扫描：约 1~3 分钟。跳过系统核心目录，只收集值得关注的文件。\n"
            "深度全盘扫描：约 5~30 分钟（取决于磁盘文件总量）。遍历全部目录，结果最全。\n"
            "扫描过程中可以随时暂停或终止，已扫描的结果会保留。"))
        h = QLabel("扫描过程中可随时暂停/终止，已扫描结果会保留。")
        h.setObjectName("sub")
        hint.addWidget(h)
        hint.addStretch(1)
        lay.addLayout(hint)

        # 快捷操作
        card = make_card()
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(12)
        lbl = QLabel("快捷操作")
        lbl.setObjectName("h2")
        cl.addWidget(lbl)
        cl.addStretch(1)
        b_set = QPushButton("⚙️ 设置")
        b_help = QPushButton("❓ 帮助说明")
        b_sc = QPushButton("🖱️ 创建桌面快捷方式")
        b_open = QPushButton("📄 打开最近报告")
        b_set.clicked.connect(self.open_settings)
        b_help.clicked.connect(self.show_help)
        b_sc.clicked.connect(self.create_shortcut)
        b_open.clicked.connect(self.open_report)
        cl.addWidget(b_set)
        cl.addWidget(b_help)
        cl.addWidget(b_sc)
        cl.addWidget(b_open)
        lay.addWidget(card)
        lay.addStretch(1)

        self.btn_open_report = b_open

    def refresh_drives(self) -> None:
        for w in self.drives:
            w.refresh()
