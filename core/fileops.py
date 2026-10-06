# -*- coding: utf-8 -*-
"""批量文件操作：移入回收站 / 彻底删除（可还原）/ 备份 / 迁移 / 还原。

安全原则：
- 只对调用方传入的路径操作，绝不自行扩散；
- 操作前复核占用与锁定状态；
- 全部操作写日志。
"""
from __future__ import annotations

import ctypes
import datetime
import os
import shutil
import time
from ctypes import Structure, byref, c_int, c_uint, c_void_p, c_wchar_p, windll
from typing import Callable, Iterable, List, Optional, Tuple

from .config import appdata_dir
from .logger import write_log
from .occupancy import is_locked


# ---------- 移入回收站 ----------
class SHFILEOPSTRUCTW(Structure):
    _fields_ = [
        ("hwnd", c_void_p),
        ("wFunc", c_uint),
        ("pFrom", c_wchar_p),
        ("pTo", c_wchar_p),
        ("fFlags", c_uint),
        ("fAnyOperationsAborted", c_int),
        ("hNameMappings", c_void_p),
        ("lpszProgressTitle", c_wchar_p),
    ]


FO_DELETE = 3
FOF_ALLOWUNDO = 0x40
FOF_NOCONFIRMATION = 0x10
FOF_NOERRORUI = 0x400
FOF_SILENT = 0x4
FOF_NOCONFIRMMKDIR = 0x200


def delete_to_recycle(paths: List[str]) -> Tuple[bool, str]:
    """将文件/文件夹移入回收站。返回 (是否全部成功, 错误信息)。"""
    if not paths:
        return True, ""
    p_from = "\0".join(paths) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = p_from
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    try:
        result = windll.shell32.SHFileOperationW(byref(op))
        if result == 0 and not op.fAnyOperationsAborted:
            return True, ""
        return False, f"操作被取消或部分失败（错误码 {result}）"
    except Exception as e:
        return False, str(e)


# ---------- 彻底删除（移入工具内部回收箱，可还原） ----------
def trash_root() -> str:
    p = os.path.join(appdata_dir(), "trash")
    os.makedirs(p, exist_ok=True)
    return p


def trash_batch_dir() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = os.path.join(trash_root(), ts)
    os.makedirs(p, exist_ok=True)
    return p


def _dest_under(src: str, dest_base: str) -> str:
    """在 dest_base 下按盘符+相对路径保留原结构。"""
    drive = src[:2].replace(":", "_")
    rel = src[3:] if len(src) > 3 else ""
    return os.path.join(dest_base, drive, rel)


# ---------- 通用 ----------
def _verify_operable(entry_path: str) -> Optional[str]:
    """返回不可操作原因；None 表示可操作。"""
    locked = is_locked(entry_path)
    if locked:
        return "文件正被其他程序占用"
    return None


def run_batch(items: List[dict], op: str, options: dict,
              progress_cb: Optional[Callable[[int, int, dict], None]] = None,
              cancel: Optional[Callable[[], bool]] = None) -> List[dict]:
    """执行批量操作。

    items: [{"path":..., "size":...}]  仅这些条目会被处理
    op: "delete_recycle" / "delete_permanent" / "backup" / "migrate" / "restore"
    options: 各操作参数
    返回逐条结果 [{"path","ok","msg"}]
    """
    results: List[dict] = []
    total = len(items)
    for i, item in enumerate(items):
        if cancel and cancel():
            break
        p = item["path"]
        res = _do_one(p, op, options)
        results.append({"path": p, "ok": res[0], "msg": res[1]})
        if progress_cb:
            progress_cb(i + 1, total, res)
    return results


def _do_one(path: str, op: str, options: dict) -> Tuple[bool, str]:
    if op == "delete_recycle":
        reason = _verify_operable(path)
        if reason:
            write_log("delete_recycle", path, "failed", reason)
            return False, reason
        ok, msg = delete_to_recycle([path])
        write_log("delete_recycle", path, "success" if ok else "failed", msg)
        return ok, msg or "已移入回收站"

    if op == "delete_permanent":
        reason = _verify_operable(path)
        if reason:
            write_log("delete_permanent", path, "failed", reason)
            return False, reason
        try:
            batch = options.get("batch_dir") or trash_batch_dir()
            dest = _dest_under(path, batch)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.isdir(path):
                shutil.move(path, dest)
            else:
                shutil.move(path, dest)
            write_log("delete_permanent", path, "success", "已移入安全回收箱", trash_path=dest)
            return True, f"已移入安全回收箱（可在操作历史中还原）-> {dest}"
        except Exception as e:
            write_log("delete_permanent", path, "failed", str(e))
            return False, str(e)

    if op == "backup":
        try:
            dest_root = options.get("dest") or ""
            if not dest_root:
                return False, "未选择备份目录"
            base = os.path.join(dest_root,
                                "备份_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            dest = _dest_under(path, base)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            _copy_path(path, dest)
            write_log("backup", path, "success", "已备份", target_path=dest)
            return True, f"已备份到 {dest}"
        except Exception as e:
            write_log("backup", path, "failed", str(e))
            return False, str(e)

    if op == "migrate":
        try:
            dest_root = options.get("dest") or ""
            if not dest_root:
                return False, "未选择迁移目标目录"
            base = os.path.join(dest_root,
                                "迁移_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            dest = _dest_under(path, base)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            _copy_path(path, dest)
            if options.get("delete_original"):
                reason = _verify_operable(path)
                if reason:
                    return False, f"已复制到目标，但原文件被占用无法删除：{reason}"
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
                write_log("migrate", path, "success", "已迁移（原文件已删除）", target_path=dest)
                return True, f"已迁移并删除原文件 -> {dest}"
            write_log("migrate", path, "success", "已复制（保留原文件）", target_path=dest)
            return True, f"已复制（原文件保留） -> {dest}"
        except Exception as e:
            write_log("migrate", path, "failed", str(e))
            return False, str(e)

    if op == "restore":
        try:
            src = options.get("trash_path") or path
            dst = options.get("original") or path
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            write_log("restore", dst, "success", "已从安全回收箱还原", target_path=dst)
            return True, "已还原"
        except Exception as e:
            write_log("restore", path, "failed", str(e))
            return False, str(e)

    return False, f"未知操作: {op}"


def _copy_path(src: str, dest: str) -> None:
    if os.path.isdir(src):
        shutil.copytree(src, dest)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)


def empty_trash() -> Tuple[int, int]:
    """清空安全回收箱。返回 (删除项数, 失败项数)。"""
    root = trash_root()
    ok = fail = 0
    for name in os.listdir(root):
        p = os.path.join(root, name)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=False)
            else:
                os.remove(p)
            ok += 1
        except Exception:
            fail += 1
    return ok, fail


def list_trash_batches() -> List[dict]:
    """列出安全回收箱中的批次（用于还原）。"""
    root = trash_root()
    out = []
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if os.path.isdir(p) and name[:8].isdigit():
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _, fs in os.walk(p) for f in fs)
            out.append({"batch": name, "path": p, "size": size})
    out.sort(key=lambda x: x["batch"], reverse=True)
    return out


def list_trash_items(batch: str) -> List[Tuple[str, str, str]]:
    """返回某批次内 [(真实原路径, 回收箱路径, 是否目录)]。"""
    root = os.path.join(trash_root(), batch)
    items = []
    drive_map = {"c_": "C:\\", "d_": "D:\\", "e_": "E:\\", "f_": "F:\\"}
    for dp, _, fs in os.walk(root):
        for f in fs:
            tp = os.path.join(dp, f)
            items.append(("", tp, False))
        for d in os.listdir(dp):
            tp = os.path.join(dp, d)
            if os.path.isdir(tp) and tp not in [i[1] for i in items]:
                items.append(("", tp, True))
    # 推导原路径
    for i, it in enumerate(items):
        tp = it[1]
        rel = os.path.relpath(tp, root)
        parts = rel.split(os.sep)
        if parts:
            drive = drive_map.get(parts[0].lower(), parts[0] + ":\\")
            orig = os.path.join(drive, *parts[1:])
            items[i] = (orig, tp, it[2])
    return items
