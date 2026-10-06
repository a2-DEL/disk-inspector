# -*- coding: utf-8 -*-
"""页面2：扫描进度页（含后台扫描线程）。"""
from __future__ import annotations

import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from core.config import AppConfig
from core.model import ScanResult
from core.scanner import scan
from core.occupancy import disk_usage
from ui.widgets import HelpTip, make_card


class ScanWorker(QThread):
    prog = pyqtSignal(dict)
    done = pyqtSignal(object)

    def __init__(self, roots, cfg: AppConfig, mode: str):
        super().__init__()
        self.roots = roots
        self.cfg = cfg
        self.mode = mode
        self.stop_ev = threading.Event()
        self.pause_ev = threading.Event()

    def run(self) -> None:
        try:
            res = scan(self.roots, self.cfg, self.mode,
                       progress_cb=self.prog.emit,
                       stop_event=self.stop_ev, pause_event=self.pause_ev)
            # 索引构建在扫描线程完成（纯 dict/list 操作，线程安全），
            # 避免主线程处理数百万条目时的内存峰值与长时间阻塞（异常也可在此捕获）。
            res.build_index()
            self.done.emit(res)
        except Exception as e:
            import traceback
            traceback.print_exc()
            res = ScanResult(mode=self.mode, roots=self.roots)
            res.stats = {"error": str(e)}
            self.done.emit(res)


class ScanPage(QWidget):
    finished = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._worker = None
        self._t0 = 0.0
        self._last = {}
        self._frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
        self._fi = 0
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 22, 24, 22)
        cl.setSpacing(14)

        head = QHBoxLayout()
        self.spinner = QLabel("⠋")
        self.spinner.setStyleSheet("font-size:26px;color:#2D7FF9;font-weight:700;")
        self.title = QLabel("正在扫描磁盘…")
        self.title.setObjectName("h2")
        head.addWidget(self.spinner)
        head.addWidget(self.title)
        head.addStretch(1)
        self.btn_pause = QPushButton("⏸ 暂停")
        self.btn_stop = QPushButton("⏹ 终止")
        head.addWidget(self.btn_pause)
        head.addWidget(self.btn_stop)
        cl.addLayout(head)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        cl.addWidget(self.bar)

        info = QHBoxLayout()
        info.setSpacing(20)
        self.lbl_dir = QLabel("当前目录：-")
        self.lbl_dir.setObjectName("sub")
        self.lbl_dir.setWordWrap(True)
        info.addWidget(self.lbl_dir, 3)
        cl.addLayout(info)

        stats = QGridLayout()
        stats.setSpacing(8)
        self.s_files = QLabel("0")
        self.s_files.setObjectName("bigNum")
        self.s_size = QLabel("0 B")
        self.s_size.setObjectName("bigNum")
        self.s_large = QLabel("0")
        self.s_large.setObjectName("bigNum")
        self.s_junk = QLabel("0")
        self.s_junk.setObjectName("bigNum")
        self.s_time = QLabel("0 秒")
        self.s_eta = QLabel("-")
        for c, (t, w) in enumerate([
            ("已扫描文件数", self.s_files), ("已扫描容量", self.s_size),
            ("发现大文件", self.s_large), ("可清理项", self.s_junk),
            ("已耗时", self.s_time), ("预计剩余", self.s_eta)]):
            box = QVBoxLayout()
            box.addWidget(w)
            lbl = QLabel(t)
            lbl.setObjectName("sub")
            box.addWidget(lbl)
            stats.addLayout(box, c // 3, c % 3)
        cl.addLayout(stats)

        tip = QHBoxLayout()
        tip.addWidget(HelpTip("极速/深度扫描说明见首页提示。扫描过程中随时可暂停或终止；终止后已扫到的结果仍会保留。"))
        t = QLabel("提示：扫描到的系统核心目录已被自动跳过或锁定，不会出现在可操作列表中。")
        t.setObjectName("sub")
        tip.addWidget(t)
        tip.addStretch(1)
        cl.addLayout(tip)

        lay.addWidget(card)
        lay.addStretch(1)

        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_stop.clicked.connect(self._stop)

        from PyQt6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    # ---------- 动画 ----------
    def _tick(self) -> None:
        self._fi = (self._fi + 1) % len(self._frames)
        self.spinner.setText(self._frames[self._fi])
        if self._worker and self._last:
            d = self._last
            self.s_time.setText(self._fmt_sec(d.get("elapsed", 0)))
            eta = d.get("eta") or 0
            self.s_eta.setText(self._fmt_sec(eta) if eta > 0 else "-")

    @staticmethod
    def _fmt_sec(sec: float) -> str:
        sec = int(sec)
        if sec < 60:
            return f"{sec} 秒"
        return f"{sec // 60} 分 {sec % 60} 秒"

    # ---------- 扫描控制 ----------
    def start(self, roots, cfg: AppConfig, mode: str) -> None:
        self._t0 = time.time()
        self._last = {}
        self.bar.setValue(0)
        self.s_files.setText("0")
        self.s_size.setText("0 B")
        self.s_large.setText("0")
        self.s_junk.setText("0")
        self.lbl_dir.setText("正在准备…")
        self.title.setText("正在扫描磁盘…")
        self.btn_pause.setText("⏸ 暂停")
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self._worker = ScanWorker(roots, cfg, mode)
        self._worker.prog.connect(self._on_prog)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_prog(self, d: dict) -> None:
        self._last = d
        self.s_files.setText(str(d.get("files", 0)))
        self.s_size.setText(_fsize(d.get("size", 0)))
        self.s_large.setText(str(d.get("large", 0)))
        self.s_junk.setText(str(d.get("junk", 0)))
        total = self._total_used()
        if total > 0:
            self.bar.setValue(min(int(d.get("size", 0) / total * 1000), 999))
        if self._worker:
            self.lbl_dir.setText(f"正在扫描：{d.get('dir') or '…'}")

    def _total_used(self) -> int:
        total = 0
        for r in (self._worker.roots if self._worker else []):
            du = disk_usage(r) or {}
            total += du.get("used", 0)
        return total

    def _on_done(self, result: ScanResult) -> None:
        self._last = {}
        self.title.setText("扫描完成 ✓")
        self.spinner.setText("✅")
        self.bar.setValue(1000)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        if result.stats.get("error"):
            self.title.setText("扫描出错")
        self.finished.emit(result)

    def _toggle_pause(self) -> None:
        if not self._worker:
            return
        if self._worker.pause_ev.is_set():
            self._worker.pause_ev.clear()
            self.btn_pause.setText("⏸ 暂停")
        else:
            self._worker.pause_ev.set()
            self.btn_pause.setText("▶ 继续")

    def _stop(self) -> None:
        if not self._worker:
            return
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.title.setText("正在终止…")
        self._worker.stop_ev.set()


def _fsize(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"
