# -*- coding: utf-8 -*-
"""通用界面组件：卡片、统计卡、帮助提示、盘符占用条。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QToolTip, QVBoxLayout, QWidget,
)

from core.occupancy import disk_usage


def make_card(parent: QWidget = None) -> QFrame:
    c = QFrame(parent)
    c.setObjectName("card")
    c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return c


class StatCard(QFrame):
    """统计卡片：大数字 + 说明。color: blue/red/green/orange/gray。"""

    def __init__(self, label: str, color: str = "blue", parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(2)
        self.num = QLabel("0")
        self.num.setObjectName("bigNum")
        self.num.setStyleSheet({"blue": "", "red": "", "green": "", "orange": ""}[color])
        if color == "red":
            self.num.setObjectName("warn")
        elif color == "green":
            self.num.setObjectName("good")
        elif color == "orange":
            self.num.setObjectName("org")
        elif color == "gray":
            self.num.setStyleSheet("color:#8B949E;font-size:26px;font-weight:700;")
        self.lbl = QLabel(label)
        self.lbl.setObjectName("sub")
        lay.addWidget(self.num)
        lay.addWidget(self.lbl)

    def set_value(self, text: str) -> None:
        self.num.setText(text)


class HelpTip(QLabel):
    """带悬浮说明的 ? 图标。"""

    def __init__(self, text: str, parent: QWidget = None):
        super().__init__("  ?  ", parent)
        self.setToolTip(text)
        self.setStyleSheet(
            "color:#2D7FF9;font-weight:700;border:1px solid #B9D4FB;"
            "border-radius:9px;padding:0 5px;background:#E8F1FE;cursor:help;")
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._tip = text

    def enterEvent(self, e):
        QToolTip.showText(self.mapToGlobal(self.rect().center()), self._tip, self)
        super().enterEvent(e)


class DriveUsage(QFrame):
    """单个盘符的已用/剩余空间展示条。"""

    def __init__(self, drive: str, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.drive = drive
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        self.title = QLabel(drive)
        self.title.setObjectName("h2")
        self.percent = QLabel("")
        self.percent.setObjectName("sub")
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.percent)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1000)
        self.detail = QLabel("正在读取…")
        self.detail.setObjectName("sub")
        lay.addLayout(top)
        lay.addWidget(self.bar)
        lay.addWidget(self.detail)
        self.refresh()

    def refresh(self) -> None:
        du = disk_usage(self.drive)
        if not du or du["total"] <= 0:
            self.detail.setText("无法读取（盘符不存在或未就绪）")
            return
        used, total = du["used"], du["total"]
        pct = used / total * 100
        self.percent.setText(f"{pct:.1f}%")
        self.bar.setValue(int(pct * 10))
        gb = 1024 ** 3

        def fs(n):
            if n >= gb:
                return f"{n / gb:.1f} GB"
            return f"{n / 1024 ** 2:.0f} MB"

        self.detail.setText(f"已用 {fs(used)} / 共 {fs(total)}，剩余 {fs(total - used)}")
