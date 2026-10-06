# -*- coding: utf-8 -*-
"""页面4：批量操作页 —— 只对已勾选条目生效，严禁处理未勾选文件。"""
from __future__ import annotations

import os

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from core import fileops, logger
from core.report import fmt_size, fmt_time
from ui.widgets import StatCard, make_card


class OpWorker(QThread):
    prog = pyqtSignal(int, int, dict)
    done = pyqtSignal(list)

    def __init__(self, items, op: str, options: dict):
        super().__init__()
        self.items = items
        self.op = op
        self.options = options

    def run(self) -> None:
        results = fileops.run_batch(
            self.items, self.op, self.options,
            progress_cb=lambda i, t, r: self.prog.emit(i, t, r))
        self.done.emit(results)


class BatchPage(QWidget):
    def __init__(self, store, parent: QWidget = None):
        super().__init__(parent)
        self.store = store
        self._worker = None
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # 勾选总览
        head = make_card()
        h = QHBoxLayout(head)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)
        self.sel_sum = QLabel("当前勾选：0 项 · 0 B")
        self.sel_sum.setObjectName("h2")
        h.addWidget(self.sel_sum)
        h.addStretch(1)
        b_refresh = QPushButton("↻ 刷新勾选")
        b_import = QPushButton("📥 导入勾选清单（JSON）")
        b_history = QPushButton("🕘 操作历史")
        b_log = QPushButton("📄 导出日志")
        b_refresh.clicked.connect(self._refresh_summary)
        b_import.clicked.connect(self._import_manifest)
        b_history.clicked.connect(self._show_history)
        b_log.clicked.connect(self._export_log)
        h.addWidget(b_refresh)
        h.addWidget(b_import)
        h.addWidget(b_history)
        h.addWidget(b_log)
        lay.addWidget(head)

        # 预览表 + 日志
        split = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tip = QLabel("⚠️ 以下操作【只对勾选条目】生效，未勾选的文件绝对不会被处理。系统高危文件已锁定，无法勾选。")
        tip.setStyleSheet("background:#FEF6E7;color:#B45309;border-radius:8px;padding:8px 12px;")
        tl.addWidget(tip)
        self.preview = QTableWidget()
        self.preview.setColumnCount(5)
        self.preview.setHorizontalHeaderLabels(["路径", "类型", "大小", "风险", "处理建议"])
        self.preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.verticalHeader().setVisible(False)
        self.preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.preview.setAlternatingRowColors(True)
        tl.addWidget(self.preview, 1)
        split.addWidget(top)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        ops = QHBoxLayout()
        ops.setSpacing(10)
        ops.addWidget(self._build_delete_card(), 1)
        ops.addWidget(self._build_backup_card(), 1)
        ops.addWidget(self._build_migrate_card(), 1)
        bl.addLayout(ops)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        bl.addWidget(self.bar)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setPlaceholderText("操作日志将实时显示在这里…")
        bl.addWidget(self.log)
        split.addWidget(bottom)
        split.setSizes([320, 420])
        lay.addWidget(split, 1)

        self._refresh_summary()

    # ---------- 三个操作卡片 ----------
    def _build_delete_card(self):
        c = make_card()
        l = QVBoxLayout(c)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(8)
        t = QLabel("🗑️ 安全删除")
        t.setObjectName("h2")
        l.addWidget(t)
        self.rb_recycle = QRadioButton("移入回收站（推荐，可恢复）")
        self.rb_recycle.setChecked(True)
        self.rb_permanent = QRadioButton("彻底删除（先移入本工具安全回收箱，可还原）")
        l.addWidget(self.rb_recycle)
        l.addWidget(self.rb_permanent)
        b = QPushButton("执行删除")
        b.setObjectName("danger")
        b.clicked.connect(self._do_delete)
        l.addWidget(b)
        h = QLabel("仅删除你勾选的条目；占用中的文件会被自动跳过。")
        h.setObjectName("sub")
        h.setWordWrap(True)
        l.addWidget(h)
        return c

    def _build_backup_card(self):
        c = make_card()
        l = QVBoxLayout(c)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(8)
        t = QLabel("💾 批量备份")
        t.setObjectName("h2")
        l.addWidget(t)
        row = QHBoxLayout()
        self.backup_dir = QLineEdit()
        self.backup_dir.setPlaceholderText("选择备份目录")
        self.backup_dir.setText(self.store.cfg.backup_dir_resolved)
        b_b = QPushButton("浏览")
        b_b.clicked.connect(self._pick_backup_dir)
        row.addWidget(self.backup_dir)
        row.addWidget(b_b)
        l.addLayout(row)
        self.cb_zip = QCheckBox("备份完成后打包为 ZIP（可选）")
        l.addWidget(self.cb_zip)
        b = QPushButton("执行备份")
        b.setObjectName("primary")
        b.clicked.connect(self._do_backup)
        l.addWidget(b)
        h = QLabel("按扫描时间自动新建子文件夹，保留原始目录结构。")
        h.setObjectName("sub")
        h.setWordWrap(True)
        l.addWidget(h)
        return c

    def _build_migrate_card(self):
        c = make_card()
        l = QVBoxLayout(c)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(8)
        t = QLabel("🚚 批量迁移")
        t.setObjectName("h2")
        l.addWidget(t)
        row = QHBoxLayout()
        self.mig_dir = QLineEdit()
        self.mig_dir.setPlaceholderText("选择迁移目标目录")
        b_b = QPushButton("浏览")
        b_b.clicked.connect(self._pick_mig_dir)
        row.addWidget(self.mig_dir)
        row.addWidget(b_b)
        l.addLayout(row)
        self.cb_del_orig = QCheckBox("迁移完成后删除原文件（可释放空间）")
        l.addWidget(self.cb_del_orig)
        b = QPushButton("执行迁移")
        b.setObjectName("primary")
        b.clicked.connect(self._do_migrate)
        l.addWidget(b)
        h = QLabel("软件依赖文件（不可迁移）与占用中的文件会被自动跳过。")
        h.setObjectName("sub")
        h.setWordWrap(True)
        l.addWidget(h)
        return c

    def _pick_backup_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择备份目录", self.backup_dir.text() or os.path.expanduser("~"))
        if d:
            self.backup_dir.setText(d)

    def _pick_mig_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择迁移目标目录", os.path.expanduser("~"))
        if d:
            self.mig_dir.setText(d)

    # ---------- 勾选与预览 ----------
    def _selection_items(self):
        """从勾选中解析出可执行条目列表。"""
        res = self.store.result
        items = []
        skipped = 0
        for p in list(self.store.selection):
            e = res.by_path.get(p) if res else None
            if e is None:
                continue
            if e.locked or e.occupied:
                skipped += 1
                continue
            items.append({"path": e.path, "size": e.size, "entry": e})
        return items, skipped

    def _refresh_summary(self) -> None:
        res = self.store.result
        n = len(self.store.selection)
        s = 0
        if res:
            for p in self.store.selection:
                e = res.by_path.get(p)
                if e:
                    s += e.size
        self.sel_sum.setText(f"当前勾选：{n} 项 · {fmt_size(s)}")
        self._fill_preview()

    def _fill_preview(self) -> None:
        items, _ = self._selection_items()
        self.preview.setRowCount(len(items))
        for i, it in enumerate(items):
            e = it["entry"]
            self.preview.setItem(i, 0, QTableWidgetItem(e.path))
            self.preview.setItem(i, 1, QTableWidgetItem("文件夹" if e.is_dir else e.ext.upper().lstrip(".") or "-"))
            self.preview.setItem(i, 2, QTableWidgetItem(fmt_size(e.size)))
            self.preview.setItem(i, 3, QTableWidgetItem(e.risk_label))
            self.preview.setItem(i, 4, QTableWidgetItem(e.advice or "-"))

    def _import_manifest(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "导入勾选清单", "", "JSON 清单 (*.json)")
        if not fn:
            return
        try:
            import json
            with open(fn, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("app") != "磁盘文件检视工具" or not data.get("items"):
                QMessageBox.warning(self, "导入失败", "该文件不是有效的勾选清单。")
                return
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法读取清单：{e}")
            return
        res = self.store.result
        added = skipped = 0
        for it in data.get("items", []):
            p = it.get("path", "")
            if not p:
                continue
            if res and res.by_path.get(p):
                e = res.by_path[p]
                if e.locked or e.occupied:
                    skipped += 1
                    continue
            elif res:
                skipped += 1
                continue
            self.store.selection.add(p)
            added += 1
        self._refresh_summary()
        self._log(f"📥 导入清单 {fn}：新增勾选 {added} 项，跳过（锁定/占用/不在本次扫描中）{skipped} 项。")

    # ---------- 执行操作 ----------
    def _confirm(self, title: str, items, extra: str = "") -> bool:
        n = len(items)
        s = sum(i["size"] for i in items)
        preview = "\n".join(i["path"] for i in items[:8])
        more = "" if n <= 8 else f"\n…… 等共 {n} 项"
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"即将对勾选的 {n} 项（共 {fmt_size(s)}）执行操作：")
        box.setInformativeText(f"{preview}{more}\n\n{extra}\n\n⚠️ 未勾选的文件绝对不会被处理。")
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Ok

    def _do_delete(self) -> None:
        items, skipped = self._selection_items()
        if not items:
            QMessageBox.information(self, "没有可操作项", "当前勾选为空，或全部为锁定/占用文件。")
            return
        permanent = self.rb_permanent.isChecked()
        mode = "彻底删除" if permanent else "移入回收站"
        if not self._confirm("删除确认", items, f"方式：{mode}\n移入回收站可从系统回收站恢复；彻底删除会先移入本工具安全回收箱（可在操作历史中还原）。"):
            return
        if permanent:
            box = QMessageBox(self)
            box.setWindowTitle("二次确认")
            box.setIcon(QMessageBox.Icon.Critical)
            box.setText("二次确认：你确定要彻底删除这些文件吗？")
            box.setInformativeText("文件会先移入【本工具安全回收箱】，在安全回收箱清空前仍可还原。\n\n"
                                   f"共 {len(items)} 项，合计 {fmt_size(sum(i['size'] for i in items))}。")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return
        options = {"batch_dir": fileops.trash_batch_dir()} if permanent else {}
        self._run_op(items, "delete_permanent" if permanent else "delete_recycle", options,
                     f"删除（{mode}）")

    def _do_backup(self) -> None:
        items, skipped = self._selection_items()
        if not items:
            QMessageBox.information(self, "没有可操作项", "当前勾选为空。")
            return
        dest = self.backup_dir.text().strip()
        if not dest:
            QMessageBox.warning(self, "缺少目录", "请先选择备份目录。")
            return
        if not self._confirm("备份确认", items, f"备份到：{dest}\n将保留原始目录结构。"):
            return
        self._run_op(items, "backup", {"dest": dest}, "备份")

    def _do_migrate(self) -> None:
        items, skipped = self._selection_items()
        if not items:
            QMessageBox.information(self, "没有可操作项", "当前勾选为空。")
            return
        dest = self.mig_dir.text().strip()
        if not dest:
            QMessageBox.warning(self, "缺少目录", "请先选择迁移目标目录。")
            return
        block = [i for i in items if not i["entry"].can_migrate]
        if block:
            QMessageBox.warning(self, "含不可迁移文件",
                                f"其中有 {len(block)} 项为软件依赖文件，禁止迁移，将自动跳过：\n"
                                + "\n".join(b["path"] for b in block[:5]))
            items = [i for i in items if i["entry"].can_migrate]
        if not items:
            return
        mode = "迁移后删除原文件" if self.cb_del_orig.isChecked() else "复制到目标（保留原文件）"
        if not self._confirm("迁移确认", items, f"目标目录：{dest}\n方式：{mode}"):
            return
        self._run_op(items, "migrate",
                     {"dest": dest, "delete_original": self.cb_del_orig.isChecked()},
                     f"迁移（{mode}）")

    def _run_op(self, items, op: str, options: dict, label: str) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "忙", "有操作正在执行，请稍候。")
            return
        self.bar.setVisible(True)
        self.bar.setRange(0, len(items))
        self.bar.setValue(0)
        self._log(f"▶ 开始{label}：{len(items)} 项")
        self._worker = OpWorker(items, op, options)
        self._worker.prog.connect(self._on_prog)
        self._worker.done.connect(lambda r, o=op: self._on_done(r, o))
        self._worker.start()

    def _on_prog(self, done: int, total: int, res: dict) -> None:
        self.bar.setValue(done)
        p = res.get("path", "")
        if res.get("ok"):
            self._log(f"  ✅ {p}  {res.get('msg', '')}")
        else:
            self._log(f"  ❌ {p}  失败：{res.get('msg', '')}")

    def _on_done(self, results: list, op: str) -> None:
        self.bar.setVisible(False)
        ok = sum(1 for r in results if r["ok"])
        fail = len(results) - ok
        self._log(f"✔ {op}完成：成功 {ok} 项，失败 {fail} 项。失败原因已记录到日志。")
        self._refresh_summary()
        if fail:
            QMessageBox.warning(self, "部分失败", f"{op}完成：成功 {ok} 项，失败 {fail} 项。\n失败的条目通常因文件被占用或权限不足，详见操作日志。")
        else:
            QMessageBox.information(self, "完成", f"{op}完成：成功 {ok} 项。")

    # ---------- 日志 ----------
    def _log(self, text: str) -> None:
        self.log.append(text)

    def _export_log(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "导出操作日志", "操作日志.txt", "文本文件 (*.txt)")
        if fn:
            p = logger.export_logs(fn)
            self._log(f"📄 日志已导出：{p}" if p else "❌ 日志导出失败")

    # ---------- 操作历史 ----------
    def _show_history(self) -> None:
        dlg = HistoryDialog(self)
        dlg.exec()

    def refresh(self) -> None:
        self._refresh_summary()


class HistoryDialog(QDialog):
    """操作历史：查看日志、还原安全回收箱文件、清空回收箱。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("操作历史")
        self.resize(900, 520)
        lay = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["时间", "操作", "路径", "状态", "说明", "还原路径"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table)
        btns = QHBoxLayout()
        b_restore = QPushButton("♻️ 还原选中（安全回收箱）")
        b_empty = QPushButton("🧹 清空安全回收箱")
        b_refresh = QPushButton("↻ 刷新")
        b_close = QPushButton("关闭")
        b_restore.clicked.connect(self._restore)
        b_empty.clicked.connect(self._empty)
        b_refresh.clicked.connect(self._load)
        b_close.clicked.connect(self.accept)
        btns.addWidget(b_restore)
        btns.addWidget(b_empty)
        btns.addStretch(1)
        btns.addWidget(b_refresh)
        btns.addWidget(b_close)
        lay.addLayout(btns)
        self._load()

    def _load(self) -> None:
        logs = logger.read_logs(1000)
        self._logs = logs
        self.table.setRowCount(len(logs))
        for i, r in enumerate(logs):
            vals = [r.get("time", ""),
                    {"delete_recycle": "移入回收站", "delete_permanent": "彻底删除",
                     "backup": "备份", "migrate": "迁移", "restore": "还原"}.get(r.get("op", ""), r.get("op", "")),
                    r.get("path", ""),
                    "成功" if r.get("status") == "success" else "失败",
                    r.get("detail", ""),
                    r.get("trash_path", "")]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c == 3 and r.get("status") != "success":
                    it.setForeground(Qt.GlobalColor.red)
                self.table.setItem(i, c, it)

    def _restore(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedItems()})
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要还原的记录（彻底删除成功的记录）。")
            return
        items = []
        for r in rows:
            rec = self._logs[r]
            if rec.get("op") == "delete_permanent" and rec.get("status") == "success" and rec.get("trash_path"):
                items.append({"path": rec["trash_path"], "trash_path": rec["trash_path"], "original": rec["path"]})
        if not items:
            QMessageBox.information(self, "提示", "选中的记录中没有可还原的彻底删除条目。")
            return
        if not QMessageBox.question(self, "还原确认", f"将还原 {len(items)} 个条目到原位置，继续？") == QMessageBox.StandardButton.Yes:
            return
        for it in items:
            try:
                import shutil
                os.makedirs(os.path.dirname(it["original"]), exist_ok=True)
                shutil.move(it["trash_path"], it["original"])
                logger.write_log("restore", it["original"], "success", "已还原")
            except Exception as e:
                logger.write_log("restore", it["original"], "failed", str(e))
        self._load()

    def _empty(self) -> None:
        if QMessageBox.question(self, "清空确认",
                                "将永久删除安全回收箱中的所有内容，且无法再还原！继续？") != QMessageBox.StandardButton.Yes:
            return
        ok, fail = fileops.empty_trash()
        QMessageBox.information(self, "完成", f"已清空 {ok} 项，失败 {fail} 项。")
        self._load()
