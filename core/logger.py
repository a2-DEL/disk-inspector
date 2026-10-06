# -*- coding: utf-8 -*-
"""操作日志：JSONL 文件，记录每次删除/备份/迁移，支持历史查询与还原。"""
from __future__ import annotations

import datetime
import json
import os
from typing import List, Optional

from .config import appdata_dir


def _log_path() -> str:
    return os.path.join(appdata_dir(), "operations.log")


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(op_type: str, path: str, status: str, detail: str = "",
              trash_path: str = "", target_path: str = "") -> None:
    rec = {
        "time": _now(),
        "op": op_type,          # delete_recycle / delete_permanent / backup / migrate / restore
        "path": path,
        "status": status,       # success / failed
        "detail": detail,
        "trash_path": trash_path,   # 彻底删除时的内部回收箱路径（用于还原）
        "target_path": target_path,
    }
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_logs(limit: int = 2000) -> List[dict]:
    out: List[dict] = []
    try:
        with open(_log_path(), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out[-limit:]


def cleanup_logs(keep_days: int) -> int:
    """按保留天数清理日志，返回删除条数。"""
    if keep_days <= 0:
        return 0
    try:
        with open(_log_path(), "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
    except Exception:
        return 0
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=keep_days))
    kept = []
    removed = 0
    for line in lines:
        try:
            rec = json.loads(line)
            t = datetime.datetime.strptime(rec.get("time", ""), "%Y-%m-%d %H:%M:%S")
            if t < cutoff:
                removed += 1
                continue
        except Exception:
            pass
        kept.append(line)
    try:
        with open(_log_path(), "w", encoding="utf-8") as f:
            f.writelines(kept)
    except Exception:
        pass
    return removed


def export_logs(dest_path: str) -> Optional[str]:
    """导出日志为文本文件。"""
    try:
        with open(_log_path(), "r", encoding="utf-8") as f:
            content = f.read()
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("磁盘文件检视工具 - 操作日志\n")
            f.write("=" * 60 + "\n")
            f.write(content)
        return dest_path
    except Exception:
        return None
