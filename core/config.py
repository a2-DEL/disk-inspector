# -*- coding: utf-8 -*-
"""应用配置：读写 %APPDATA%/DiskInspector/config.json。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List


APP_NAME = "磁盘文件检视工具"
APP_DIR_NAME = "DiskInspector"


def appdata_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def resource_path(rel: str) -> str:
    """兼容源码运行与 PyInstaller 打包后的资源路径。"""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel)


@dataclass
class AppConfig:
    large_threshold_mb: int = 100
    show_hidden: bool = False
    show_protected: bool = False
    check_occupied: bool = False
    find_duplicates: bool = False
    html_dir: str = ""
    backup_dir: str = ""
    theme: str = "light"
    auto_open_report: bool = True
    log_keep_days: int = 30
    whitelist_extra: List[str] = field(default_factory=list)
    last_scan_mode: str = "fast"

    @property
    def html_dir_resolved(self) -> str:
        if self.html_dir:
            return self.html_dir
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        p = os.path.join(docs, "磁盘扫描报告")
        os.makedirs(p, exist_ok=True)
        return p

    @property
    def backup_dir_resolved(self) -> str:
        if self.backup_dir:
            return self.backup_dir
        p = os.path.join(appdata_dir(), "backup")
        os.makedirs(p, exist_ok=True)
        return p


def _cfg_path() -> str:
    return os.path.join(appdata_dir(), "config.json")


def load_config() -> AppConfig:
    cfg = AppConfig()
    try:
        with open(_cfg_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    except Exception:
        pass
    return cfg


def save_config(cfg: AppConfig) -> None:
    try:
        with open(_cfg_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
    except Exception:
        pass
