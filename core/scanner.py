# -*- coding: utf-8 -*-
"""磁盘扫描器：深度全盘扫描 / 极速扫描。

纯 Python 逻辑（无 Qt 依赖），UI 通过 QThread 调用。
支持：暂停/停止、隐藏与受保护文件过滤、大文件阈值、占用检测、重复文件检测。

稳定性设计：目录遍历采用【显式栈迭代】，不使用 Python 递归，
彻底规避超深目录树（数千层）下的 C 栈溢出 / RecursionError 导致的进程崩溃。
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from .classifier import Classifier
from .model import FileEntry, ScanResult
from .occupancy import disk_usage, file_attributes, is_locked
from .config import AppConfig

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4


class ScanContext:
    """一次扫描的上下文：规则、计数器、进度回调、控制事件。"""

    def __init__(self, cfg: AppConfig, mode: str, roots: List[str],
                 progress_cb: Optional[Callable[[dict], None]] = None,
                 stop_event: Optional[threading.Event] = None,
                 pause_event: Optional[threading.Event] = None):
        self.cfg = cfg
        self.mode = mode
        self.roots = roots
        self.classifier = Classifier()
        rules = self.classifier.rules
        self.fast_skip = [d.lower() for d in rules.get("fast_skip_dirs", [])]
        self.cache_exts = set(rules.get("cache_exts", []))
        self.residue_names = [k.lower() for k in rules.get("residue_names", [])]
        self.win_temp_top = sorted({
            s.split("\\")[0].lower() for s in rules.get("windows_temp_subdirs", [])
        })
        self.threshold = cfg.large_threshold_mb * 1024 * 1024
        self.progress_cb = progress_cb or (lambda d: None)
        self.stop_event = stop_event or threading.Event()
        self.pause_event = pause_event or threading.Event()

        # 统计
        self.files = 0
        self.dirs = 0
        self.size = 0
        self.large_count = 0
        self.junk_count = 0
        self.locked_count = 0
        self.skipped = 0
        self.cur_dir = ""
        self.entries_out: List[FileEntry] = []   # 全局条目收集列表（迭代遍历直接追加）
        self.by_category: Dict[str, int] = {}
        self.by_risk: Dict[str, int] = {}
        self.start = time.time()
        self._last_prog = 0.0
        self._total_used = 0
        for r in roots:
            du = disk_usage(r) or {}
            self._total_used += du.get("used", 0)

    # ---------- 控制 ----------
    def pause_if_needed(self) -> None:
        while self.pause_event.is_set():
            time.sleep(0.05)
            if self.stop_event.is_set():
                return

    def should_stop(self) -> bool:
        return self.stop_event.is_set()

    # ---------- 过滤 ----------
    def skip_dir(self, path: str, name: str) -> bool:
        if self.should_stop():
            return True
        self.pause_if_needed()
        pl = path.lower()
        hidden, system = self._attrs(path)
        if not self.cfg.show_hidden and hidden:
            return True
        if not self.cfg.show_protected and system:
            return True
        if self.mode == "fast":
            if any(pl == f or pl.startswith(f + "\\") for f in self.fast_skip):
                return True
            if pl.startswith("c:\\windows"):
                # 只深入 Windows 的临时/日志子目录
                if any(pl.startswith("c:\\windows\\" + t) for t in self.win_temp_top):
                    return False
                return True
        return False

    def _attrs(self, path: str) -> Tuple[bool, bool]:
        a = file_attributes(path)
        if a is None or a == -1:
            return False, False
        return bool(a & FILE_ATTRIBUTE_HIDDEN), bool(a & FILE_ATTRIBUTE_SYSTEM)

    # ---------- 文件条目 ----------
    def make_file(self, path: str, entry) -> Optional[FileEntry]:
        if self.should_stop():
            return None
        self.pause_if_needed()
        name = entry.name
        ext = os.path.splitext(name)[1].lower()
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            return None
        size = st.st_size
        ctime = st.st_ctime
        # 隐藏/系统属性过滤
        hidden, system = self._attrs(path)
        if not self.cfg.show_hidden and hidden:
            return None
        if not self.cfg.show_protected and system:
            return None
        # 极速模式：只保留值得关注的文件
        if self.mode == "fast":
            name_l = name.lower()
            is_candidate = (
                size >= self.threshold
                or ext in self.cache_exts
                or any(k in name_l for k in self.residue_names)
            )
            if not is_candidate:
                return None
        fe = self.classifier.build_entry(
            path, name, False, ext, size, ctime, self._drive(path),
            self.cfg.large_threshold_mb)
        # 占用检测：仅对“可操作候选”检测，避免拖慢全盘扫描
        if (self.cfg.check_occupied and not fe.locked
                and (fe.large or fe.category in ("temp",) or fe.residue
                     or fe.can_delete == "safe")):
            fe.occupied = is_locked(path)
        return fe

    def make_dir(self, path: str, name: str, dir_size: int,
                 child_count: int, ctime: float) -> Optional[FileEntry]:
        if self.should_stop():
            return None
        fe = self.classifier.build_entry(
            path, name, True, "", dir_size, ctime, self._drive(path),
            self.cfg.large_threshold_mb, child_count, dir_size)
        return fe

    def _drive(self, path: str) -> str:
        return path[:2] if len(path) > 1 else path

    # ---------- 统计与进度 ----------
    def count_file(self, fe: FileEntry) -> None:
        self.files += 1
        self.size += fe.size
        self.by_category[fe.category] = self.by_category.get(fe.category, 0) + 1
        self.by_risk[fe.risk] = self.by_risk.get(fe.risk, 0) + 1
        if fe.large:
            self.large_count += 1
        if fe.category in ("temp",) or fe.residue or fe.can_delete == "safe":
            self.junk_count += 1
        if fe.locked:
            self.locked_count += 1
        self._progress()

    def count_dir(self, fe: FileEntry) -> None:
        if fe is None:
            return
        self.dirs += 1
        self.by_category[fe.category] = self.by_category.get(fe.category, 0) + 1
        self.by_risk[fe.risk] = self.by_risk.get(fe.risk, 0) + 1
        if fe.locked:
            self.locked_count += 1
        self._progress()

    def _progress(self) -> None:
        now = time.time()
        if now - self._last_prog < 0.25:
            return
        self._last_prog = now
        elapsed = now - self.start
        frac = (self.size / self._total_used) if self._total_used > 0 else 0
        eta = (elapsed / frac - elapsed) if frac > 0.02 else 0
        self.progress_cb({
            "files": self.files, "size": self.size, "elapsed": elapsed,
            "eta": eta, "large": self.large_count, "junk": self.junk_count,
            "skipped": self.skipped, "dir": self.cur_dir,
        })

    def stats(self) -> dict:
        return {
            "files": self.files,
            "dirs": self.dirs,
            "size": self.size,
            "large": self.large_count,
            "junk": self.junk_count,
            "locked": self.locked_count,
            "skipped": self.skipped,
            "by_category": self.by_category,
            "by_risk": self.by_risk,
        }


def _walk_iter(root_path: str, ctx: ScanContext) -> None:
    """迭代式深度遍历（显式栈，后序生成目录条目）。

    与原递归版本结果语义完全一致：
    - 文件条目在遍历到即收集；目录条目在其全部后代处理完之后生成；
    - 目录的 dir_size = 内部全部文件字节和；child_count = 内部全部文件数；
    - 目录不可访问时跳过并计数，不影响整体扫描。

    显式栈方案不占用调用栈，无论目录嵌套多深（数千层）都不会栈溢出。
    """
    root_frame = {"path": root_path, "name": os.path.basename(root_path.rstrip("\\")) or root_path,
                  "is_root": True, "it": None, "size": 0, "count": 0}
    stack = [root_frame]
    out = ctx.entries_out
    while stack:
        if ctx.should_stop():
            return
        ctx.pause_if_needed()
        fr = stack[-1]
        # 首次进入目录：打开迭代器
        if fr["it"] is None:
            ctx.cur_dir = fr["path"]
            try:
                fr["it"] = os.scandir(fr["path"])
            except OSError:
                ctx.skipped += 1
                stack.pop()
                if not stack:
                    return
                continue
        # 取下一个条目
        try:
            e = next(fr["it"])
        except StopIteration:
            # 目录扫描完毕：生成目录条目（后序），并归并到父帧
            stack.pop()
            if not fr["is_root"]:
                try:
                    ctime = os.stat(fr["path"]).st_ctime
                except OSError:
                    ctime = 0.0
                de = ctx.make_dir(fr["path"], fr["name"], fr["size"], fr["count"], ctime)
                if de is not None:
                    out.append(de)
                    ctx.count_dir(de)
            if stack:
                pfr = stack[-1]
                pfr["size"] += fr["size"]
                pfr["count"] += fr["count"]
            continue
        except OSError:
            # 单个条目读取失败：跳过该条目继续
            continue
        # 处理当前条目
        try:
            if e.is_symlink():
                continue
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        full = os.path.join(fr["path"], e.name)
        if is_dir:
            if ctx.skip_dir(full, e.name):
                continue
            stack.append({"path": full, "name": e.name, "is_root": False,
                          "it": None, "size": 0, "count": 0})
        else:
            fe = ctx.make_file(full, e)
            if fe is None:
                continue
            out.append(fe)
            fr["size"] += fe.size
            fr["count"] += 1
            ctx.count_file(fe)


def scan(roots: List[str], cfg: AppConfig, mode: str,
         progress_cb: Optional[Callable[[dict], None]] = None,
         stop_event: Optional[threading.Event] = None,
         pause_event: Optional[threading.Event] = None) -> ScanResult:
    """执行扫描，返回 ScanResult。"""
    result = ScanResult(mode=mode, roots=[r for r in roots if r],
                        start_time=time.time())
    if not result.roots:
        result.end_time = time.time()
        return result
    ctx = ScanContext(cfg, mode, result.roots, progress_cb, stop_event, pause_event)
    for root in result.roots:
        _walk_iter(root, ctx)
        if ctx.should_stop():
            break
    result.entries = ctx.entries_out
    result.skipped_dirs = ctx.skipped
    result.stats = ctx.stats()
    result.end_time = time.time()

    # 重复文件检测（可选，哈希比对）
    if cfg.find_duplicates and mode == "deep":
        _mark_duplicates(result.entries)
        result.stats["duplicates"] = sum(1 for e in result.entries if e.duplicate)
    return result


def _mark_duplicates(entries: List[FileEntry]) -> None:
    import hashlib
    groups: Dict[Tuple[int, str], List[FileEntry]] = {}
    for e in entries:
        if e.is_dir or e.size <= 0:
            continue
        groups.setdefault((e.size, e.name.lower()), []).append(e)
    for g in groups.values():
        if len(g) < 2:
            continue
        seen = set()
        for e in g:
            try:
                h = hashlib.sha1()
                with open(e.path, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        h.update(chunk)
                digest = h.hexdigest()
            except OSError:
                continue
            if digest in seen:
                e.duplicate = True
            else:
                seen.add(digest)
