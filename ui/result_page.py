# -*- coding: utf-8 -*-
"""页面3：结果预览页（左侧目录树 + 右侧数据表格，字段与 HTML 报告一致）。"""
from __future__ import annotations

import datetime
import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.model import ScanResult
from core.report import fmt_size, fmt_time, generate_html
from ui.widgets import make_card


class ReportWorker(QThread):
    """后台线程生成 HTML 报告。

    深度扫描可达数百万条目，序列化与写文件耗时且内存占用大，
    放到后台线程执行可避免主线程卡死或内存峰值触发异常退出。
    """

    done = pyqtSignal(bool, str)

    def __init__(self, result, cfg, out_path: str, parent=None):
        super().__init__(parent)
        self._result = result
        self._cfg = cfg
        self._out = out_path

    def run(self) -> None:
        try:
            generate_html(self._result, self._cfg, self._out)
            self.done.emit(True, self._out)
        except Exception as e:
            self.done.emit(False, str(e))


class ResultPage(QWidget):
    report_ready = pyqtSignal(str)

    COLS = ["名称", "类型", "用途", "必需", "可删", "可迁移", "残留", "大文件",
            "创建时间", "大小", "大类", "风险", "处理建议"]

    def __init__(self, store, parent: QWidget = None):
        super().__init__(parent)
        self.store = store
        self._last_report = ""
        self._export_worker = None
        self._btn_html = None
        self._loading_table = False
        self._build()

    # ---------- 界面 ----------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # 工具栏
        tb = make_card()
        t = QHBoxLayout(tb)
        t.setContentsMargins(12, 10, 12, 10)
        t.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 搜索名称 / 路径 / 用途…")
        self.search.setFixedWidth(200)
        self.cb_risk = QComboBox()
        self.cb_risk.addItem("风险：全部", "")
        for v, s in [(3, "🔴 高危"), (2, "🟡 中危"), (1, "🟢 低危"), (0, "⚪ 普通")]:
            self.cb_risk.addItem(s, v)
        self.cb_cat = QComboBox()
        self.cb_cat.addItem("大类：全部", "")
        for k, s in [("system", "系统文件"), ("app", "应用软件文件"),
                     ("user", "用户个人文件"), ("temp", "临时/缓存文件"),
                     ("empty", "空文件夹"), ("other", "其他文件")]:
            self.cb_cat.addItem(s, k)
        self.cb_size = QComboBox()
        self.cb_size.addItem("大小：全部", "")
        self.cb_size.addItem("仅大型文件", "large")
        self.cb_size.addItem("仅可清理项", "junk")
        self.cb_size.addItem("仅卸载残留", "residue")
        self.cb_size.addItem("仅重复文件", "dup")
        b_all = QPushButton("全选可操作")
        b_inv = QPushButton("反选")
        b_clear = QPushButton("清空")
        b_html = QPushButton("📄 导出 HTML 报告")
        b_html.setObjectName("primary")
        b_open = QPushButton("打开报告")
        self._btn_html = b_html
        self.stat_sel = QLabel("已勾选 0 项 · 0 B")
        self.stat_sel.setStyleSheet("color:#57606A;font-weight:600;")
        t.addWidget(self.search)
        t.addWidget(self.cb_risk)
        t.addWidget(self.cb_cat)
        t.addWidget(self.cb_size)
        t.addWidget(b_all)
        t.addWidget(b_inv)
        t.addWidget(b_clear)
        t.addStretch(1)
        t.addWidget(b_html)
        t.addWidget(b_open)
        lay.addWidget(tb)

        # 统计卡片行
        cards = QHBoxLayout()
        cards.setSpacing(10)
        from ui.widgets import StatCard
        self.c_files = StatCard("当前文件夹文件数")
        self.c_size = StatCard("当前文件夹占用")
        self.c_sel = StatCard("已勾选文件数")
        self.c_selcap = StatCard("勾选总容量")
        cards.addWidget(self.c_files)
        cards.addWidget(self.c_size)
        cards.addWidget(self.c_sel)
        cards.addWidget(self.c_selcap)
        lay.addLayout(cards)

        # 树 + 表
        split = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["📁 目录", "大小", "项数"])
        self.tree.setColumnWidth(0, 300)
        self.tree.setAlternatingRowColors(True)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLS))
        tips = [
            "勾选后可进行 安全删除 / 备份 / 迁移。系统高危文件已锁定，无法勾选。",
            "文件或文件夹名称",
            "文件夹或文件后缀名",
            "该文件推测的用途说明",
            "是否系统或软件运行所必需",
            "能否安全删除：可删/谨慎/禁止",
            "能否迁移到其他磁盘",
            "是否安装/卸载残留",
            "是否超过大文件阈值",
            "创建时间",
            "文件体积",
            "文件大类",
            "风险等级",
            "处理建议",
        ]
        for c, name in enumerate(self.COLS):
            item = QTableWidgetItem(name)
            item.setToolTip(tips[c])
            self.table.setHorizontalHeaderItem(c, item)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        split.addWidget(self.tree)
        split.addWidget(self.table)
        split.setSizes([360, 1100])
        lay.addWidget(split, 1)

        self.search.textChanged.connect(lambda _: self._refresh_table())
        self.cb_risk.currentIndexChanged.connect(lambda _: self._refresh_table())
        self.cb_cat.currentIndexChanged.connect(lambda _: self._refresh_table())
        self.cb_size.currentIndexChanged.connect(lambda _: self._refresh_table())
        self.tree.currentItemChanged.connect(lambda *_: self._refresh_table())
        self.tree.itemExpanded.connect(self._on_tree_expand)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.setSortingEnabled(False)
        b_all.clicked.connect(self._sel_all)
        b_inv.clicked.connect(self._sel_invert)
        b_clear.clicked.connect(self._sel_clear)
        b_html.clicked.connect(self._export_html)
        b_open.clicked.connect(lambda: self.report_ready.emit(self._last_report))

    # ---------- 数据 ----------
    def load_result(self, result: ScanResult) -> None:
        self._last_report = ""
        self.tree.clear()
        self.table.setRowCount(0)
        self.store.selection.clear()
        if not result:
            return
        self._populate_tree()
        self._refresh_table()
        self._update_stats()

    def _populate_tree(self) -> None:
        res = self.store.result
        for root in res.roots:
            rk = root.rstrip("\\")
            node = QTreeWidgetItem([rk, "", ""])
            node.setIcon(0, _folder_icon())
            node.setData(0, Qt.ItemDataRole.UserRole, rk)
            self._ensure_children(node)
            self.tree.addTopLevelItem(node)
            node.setExpanded(True)
        self.tree.setCurrentItem(self.tree.topLevelItem(0) if self.tree.topLevelItemCount() else None)

    def _ensure_children(self, node: QTreeWidgetItem) -> None:
        path = node.data(0, Qt.ItemDataRole.UserRole)
        if node.childCount() == 0:
            res = self.store.result
            for e in res.children.get(path, []):
                if not e.is_dir:
                    continue
                child = QTreeWidgetItem([e.name, fmt_size(e.dir_size), str(e.child_count)])
                child.setIcon(0, _folder_icon())
                child.setData(0, Qt.ItemDataRole.UserRole, e.path)
                child.setToolTip(0, e.path)
                node.addChild(child)

    def _on_tree_expand(self, node: QTreeWidgetItem) -> None:
        self._ensure_children(node)

    # ---------- 右侧表格 ----------
    def _current_dir_entries(self):
        res = self.store.result
        if not res:
            return []
        item = self.tree.currentItem()
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else (res.roots[0].rstrip("\\"))
        return res.children.get(path, [])

    def _refresh_table(self) -> None:
        if not self.store.result:
            return
        self._loading_table = True
        self.table.setRowCount(0)
        q = self.search.text().strip().lower()
        risk = self.cb_risk.currentData()
        cat = self.cb_cat.currentData()
        size = self.cb_size.currentData()
        entries = self._current_dir_entries()
        self.c_files.set_value(str(len(entries)))
        self.c_size.set_value(fmt_size(sum(e.size for e in entries)))
        rows = []
        for e in entries:
            if risk != "" and e.risk != risk:
                continue
            if cat != "" and e.category != cat:
                continue
            if q and q not in e.name.lower() and q not in e.path.lower() and q not in e.purpose.lower():
                continue
            if size == "large" and not e.large:
                continue
            if size == "junk" and not (e.category == "temp" or e.residue or e.can_delete == "safe"):
                continue
            if size == "residue" and not e.residue:
                continue
            if size == "dup" and not e.duplicate:
                continue
            rows.append(e)
        self.table.setRowCount(len(rows))
        for i, e in enumerate(rows):
            self._fill_row(i, e)
        self._loading_table = False
        self._update_stats()

    def _fill_row(self, row: int, e) -> None:
        locked = e.locked or bool(e.occupied)
        cb = QTableWidgetItem()
        cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        if locked:
            cb.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cb.setCheckState(Qt.CheckState.Unchecked)
            cb.setToolTip("🔒 系统高危文件或占用中的文件，禁止操作")
        else:
            cb.setCheckState(
                Qt.CheckState.Checked if e.path in self.store.selection else Qt.CheckState.Unchecked)
        cb.setData(Qt.ItemDataRole.UserRole, e.path)
        self.table.setItem(row, 0, cb)
        name = QTableWidgetItem(("📁 " if e.is_dir else "📄 ") + e.name)
        name.setData(Qt.ItemDataRole.UserRole, e.path)
        name.setToolTip(e.path)
        if locked:
            name.setText(name.text() + " 🔒")
        self.table.setItem(row, 1, name)
        self.table.setItem(row, 2, QTableWidgetItem("文件夹" if e.is_dir else e.ext.upper().lstrip(".") or "-"))
        self.table.setItem(row, 3, QTableWidgetItem(e.purpose or "-"))
        self.table.setItem(row, 4, QTableWidgetItem(e.required_label))
        self.table.setItem(row, 5, QTableWidgetItem(e.can_delete_label))
        mig = QTableWidgetItem("可迁移" if e.can_migrate else "不可迁移")
        if not e.can_migrate:
            mig.setForeground(QBrush(QColor("#8B949E")))
        self.table.setItem(row, 6, mig)
        res = QTableWidgetItem("是" if e.residue else "否")
        self.table.setItem(row, 7, res)
        lg = QTableWidgetItem("是" if e.large else "否")
        if e.large:
            lg.setForeground(QBrush(QColor("#F5A524")))
        if e.duplicate:
            lg.setText("重复")
            lg.setForeground(QBrush(QColor("#8E4EC6")))
        self.table.setItem(row, 8, lg)
        self.table.setItem(row, 9, QTableWidgetItem(fmt_time(e.ctime)))
        sz = QTableWidgetItem(fmt_size(e.size))
        sz.setData(Qt.ItemDataRole.UserRole, e.size)
        self.table.setItem(row, 10, sz)
        self.table.setItem(row, 11, QTableWidgetItem(e.category_label))
        risk = QTableWidgetItem(e.risk_label)
        rcol = {3: "#E5484D", 2: "#F5A524", 1: "#30A46C", 0: "#8B949E"}.get(e.risk, "#8B949E")
        risk.setForeground(QBrush(QColor(rcol)))
        risk.setData(Qt.ItemDataRole.UserRole, e.risk)
        self.table.setItem(row, 12, risk)
        av = QTableWidgetItem(e.advice or "-")
        av.setToolTip(e.advice)
        self.table.setItem(row, 13, av)
        if locked:
            for c in range(self.table.columnCount()):
                it = self.table.item(row, c)
                if it:
                    it.setBackground(QBrush(QColor("#FDECEC")))

    # ---------- 勾选 ----------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table or item.column() != 0:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.store.selection.add(path)
        else:
            self.store.selection.discard(path)
        self._update_stats()

    def _sel_all(self) -> None:
        res = self.store.result
        if not res:
            return
        for e in res.entries:
            if not e.locked and not e.occupied:
                self.store.selection.add(e.path)
        self._refresh_table()
        self._update_stats()

    def _sel_invert(self) -> None:
        res = self.store.result
        if not res:
            return
        new = set()
        for e in res.entries:
            if e.locked or e.occupied:
                continue
            if e.path not in self.store.selection:
                new.add(e.path)
        self.store.selection = new
        self._refresh_table()
        self._update_stats()

    def _sel_clear(self) -> None:
        self.store.selection.clear()
        self._refresh_table()
        self._update_stats()

    def _update_stats(self) -> None:
        n = len(self.store.selection)
        s = 0
        for p in self.store.selection:
            e = self.store.result.by_path.get(p)
            if e:
                s += e.size
        self.stat_sel.setText(f"已勾选 {n} 项 · {fmt_size(s)}")
        self.c_sel.set_value(str(n))
        self.c_selcap.set_value(fmt_size(s))

    # ---------- 表格交互 ----------
    def _on_double_click(self, item: QTableWidgetItem) -> None:
        row = item.row()
        cb = self.table.item(row, 1)
        if not cb:
            return
        path = cb.data(Qt.ItemDataRole.UserRole)
        e = self.store.result.by_path.get(path)
        if e and e.is_dir:
            self._select_tree_path(path)

    def _select_tree_path(self, path: str) -> None:
        node = self._find_tree_node(self.tree.invisibleRootItem(), path)
        if node:
            self.tree.setCurrentItem(node)

    def _find_tree_node(self, parent: QTreeWidgetItem, path: str):
        for i in range(parent.childCount()):
            c = parent.child(i)
            if c.data(0, Qt.ItemDataRole.UserRole) == path:
                return c
            r = self._find_tree_node(c, path)
            if r:
                return r
        return None

    # ---------- 导出 HTML（后台线程，避免主线程卡顿与内存峰值崩溃） ----------
    def _export_html(self) -> None:
        res = self.store.result
        if not res:
            return
        if self._export_worker and self._export_worker.isRunning():
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.store.cfg.html_dir_resolved,
                           f"磁盘检视报告_{ts}.html")
        self._btn_html.setEnabled(False)
        self._btn_html.setText("⏳ 正在生成报告…")
        self._export_worker = ReportWorker(res, self.store.cfg, out)
        self._export_worker.done.connect(self._on_export_done)
        self._export_worker.start()

    def _on_export_done(self, ok: bool, info: str) -> None:
        if self._btn_html:
            self._btn_html.setEnabled(True)
            self._btn_html.setText("📄 导出 HTML 报告")
        if ok:
            self._last_report = info
            self.report_ready.emit(info)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "报告生成失败", f"生成 HTML 报告时出错：\n{info}")

    def wait_export(self, timeout_ms: int = 300000) -> bool:
        """等待导出线程结束（窗口关闭时调用，避免线程竞态崩溃）。"""
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.wait(timeout_ms)
            return not self._export_worker.isRunning()
        return True


def _folder_icon():
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#F5A524"))
    p.setPen(QColor("#D98E00"))
    p.drawRoundedRect(1, 3, 14, 11, 2, 2)
    p.drawRoundedRect(1, 1, 8, 3, 1, 1)
    p.end()
    return QIcon(pm)
