# -*- coding: utf-8 -*-
"""数据模型：文件条目与扫描结果。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# 风险等级：数值越大越危险
RISK = {"high": 3, "medium": 2, "low": 1, "normal": 0}
RISK_LABEL = {3: "高危", 2: "中危", 1: "低危", 0: "普通"}
RISK_EMOJI = {3: "🔴", 2: "🟡", 1: "🟢", 0: "⚪"}

CATEGORY_LABEL = {
    "system": "系统文件",
    "app": "应用软件文件",
    "user": "用户个人文件",
    "temp": "临时/缓存文件",
    "empty": "空文件夹",
    "other": "其他文件",
}

CAN_DELETE_LABEL = {"safe": "可删", "caution": "谨慎", "forbidden": "禁止"}
REQUIRED_LABEL = {"yes": "是", "no": "否", "unknown": "不确定"}


@dataclass(slots=True)
class FileEntry:
    """单个文件/文件夹条目。

    slots=True：全盘深度扫描可达数百万条目，去除实例 __dict__ 可显著降低内存占用，
    减少内存耗尽（MemoryError → 进程崩溃）风险。字段与行为均不变。
    """

    path: str
    name: str
    is_dir: bool = False
    ext: str = ""
    size: int = 0                      # 字节
    ctime: float = 0.0                 # 创建时间戳
    drive: str = ""                    # C: / D:
    category: str = "other"            # system/app/user/temp/empty/other
    risk: int = 0                      # 3高危 2中危 1低危 0普通
    can_delete: str = "caution"        # safe/caution/forbidden
    can_migrate: bool = True
    required: str = "unknown"          # yes/no/unknown
    residue: bool = False              # 安装/卸载残留
    large: bool = False                # 超过阈值
    duplicate: bool = False            # 重复文件
    purpose: str = ""                  # 用途说明
    advice: str = ""                   # 处理建议（小白可懂）
    locked: bool = False               # 勾选框禁用
    occupied: Optional[bool] = None    # 是否被占用 True/False/None(未检测)
    child_count: int = 0               # 文件夹直接子项数量
    dir_size: int = 0                  # 文件夹内全部文件体积和

    @property
    def risk_label(self) -> str:
        return RISK_LABEL.get(self.risk, "普通")

    @property
    def category_label(self) -> str:
        return CATEGORY_LABEL.get(self.category, "其他文件")

    @property
    def can_delete_label(self) -> str:
        return CAN_DELETE_LABEL.get(self.can_delete, "谨慎")

    @property
    def required_label(self) -> str:
        return REQUIRED_LABEL.get(self.required, "不确定")

    def to_dict(self) -> dict:
        return {
            "p": self.path,
            "n": self.name,
            "t": self.ext,
            "d": self.is_dir,
            "s": self.size,
            "c": self.ctime,
            "g": self.category,
            "r": self.risk,
            "cd": self.can_delete,
            "cm": self.can_migrate,
            "rq": self.required,
            "rs": self.residue,
            "lg": self.large,
            "dp": self.duplicate,
            "pu": self.purpose,
            "av": self.advice,
            "lk": self.locked,
            "oc": self.occupied,
        }


@dataclass
class ScanResult:
    """一次扫描的完整结果。"""

    mode: str = "fast"                 # fast / deep
    roots: List[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    entries: List[FileEntry] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    by_path: Dict[str, FileEntry] = field(default_factory=dict)
    children: Dict[str, List[FileEntry]] = field(default_factory=dict)
    skipped_dirs: int = 0

    @property
    def elapsed(self) -> float:
        return max(self.end_time - self.start_time, 0.0)

    @property
    def total_files(self) -> int:
        return self.stats.get("files", 0)

    @property
    def total_size(self) -> int:
        return self.stats.get("size", 0)

    def build_index(self) -> None:
        """根据 entries 构建 path->entry 与 children 索引。

        目录键统一为不带结尾反斜杠的父路径（如 "C:"、"C:\\Windows"）。
        """
        self.by_path = {}
        self.children = {}
        sep = "\\"
        for e in self.entries:
            self.by_path[e.path] = e
            parent = e.path.rpartition(sep)[0]
            if parent:
                self.children.setdefault(parent, []).append(e)
        # 根目录（统一不带结尾反斜杠，与父路径键一致）
        for r in self.roots:
            rkey = r.rstrip("\\")
            self.children.setdefault(rkey, [])
        # 按名称排序（文件夹在前）
        for k in self.children:
            self.children[k].sort(
                key=lambda e: (not e.is_dir, e.name.lower()))
