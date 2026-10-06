# -*- coding: utf-8 -*-
"""文件分类引擎：基于 rules.json 规则库，判定类别/风险/处理建议。

所有文案面向电脑小白，说明作用 + 给出可执行建议。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import resource_path
from .model import RISK, FileEntry


def load_rules() -> dict:
    """规则加载优先级：外部覆盖（EXE 旁 / AppData）→ 内置打包资源 → 兜底默认。"""
    import sys as _sys
    candidates = []
    if getattr(_sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(_sys.executable), "rules.json"))
    from .config import appdata_dir
    candidates.append(os.path.join(appdata_dir(), "rules.json"))
    candidates.append(resource_path(os.path.join("config", "rules.json")))
    for p in candidates:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return _FALLBACK_RULES


@dataclass
class Classification:
    category: str
    risk: int
    can_delete: str
    can_migrate: bool
    required: str
    residue: bool
    purpose: str
    advice: str
    locked: bool


class Classifier:
    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or load_rules()
        self.whitelist = [w.lower() for w in self.rules.get("whitelist", [])]
        self.cache_exts = set(self.rules.get("cache_exts", []))
        self.installer_exts = set(self.rules.get("installer_exts", []))
        self.system_exts = set(self.rules.get("system_critical_exts", []))
        self.app_code_exts = set(self.rules.get("app_code_exts", []))
        self.residue_names = [k.lower() for k in self.rules.get("residue_names", [])]
        # 路径段关键词集合：成员测试用 set，避免逐段遍历（超深路径下性能灾难）
        self.temp_keywords = set(k.lower() for k in self.rules.get("temp_dir_keywords", []))
        self.win_temp_sub = [s.lower() for s in self.rules.get("windows_temp_subdirs", [])]
        self.browser_paths = [b.lower() for b in self.rules.get("browser_cache_paths", [])]
        self.user_dirs = set(d.lower() for d in self.rules.get("user_profile_dirs", []))
        self.user_exts = {}
        for k, exts in self.rules.get("user_exts", {}).items():
            for e in exts:
                self.user_exts[e.lower()] = k
        self.purpose_map = {}
        for k, exts in self.rules.get("purpose_map", {}).items():
            for e in exts:
                self.purpose_map[e.lower()] = k
        self.advice = self.rules.get("advice_templates", {})

    # ---------- 辅助 ----------
    def _startswith_any(self, path_l: str, prefixes: List[str]) -> bool:
        for p in prefixes:
            if path_l == p or path_l.startswith(p + "\\"):
                return True
        return False

    def _segments(self, path_l: str) -> List[str]:
        return [s for s in path_l.split("\\") if s]

    def _ext_purpose(self, ext_l: str) -> str:
        if ext_l in self.user_exts:
            return self.user_exts[ext_l]
        return self.purpose_map.get(ext_l, "")

    def _fmt_mb(self, size: int, threshold_mb: int) -> str:
        gb = size / (1024 ** 3)
        mb = size / (1024 ** 2)
        if gb >= 1:
            return f"{gb:.2f} GB"
        return f"{mb:.1f} MB"

    # ---------- 主分类 ----------
    def classify(self, path: str, name: str, is_dir: bool, ext: str,
                 size: int, threshold_mb: int) -> Classification:
        path_l = path.lower()
        name_l = name.lower()
        ext_l = ext.lower()
        segs = self._segments(path_l)
        # 一次性建集合：对超深/超长路径，避免每个关键字集合都 O(段数) 遍历
        seg_set = set(segs)

        # 1) 白名单：系统核心目录
        if self._startswith_any(path_l, self.whitelist):
            return Classification(
                "system", 3, "forbidden", False, "yes", False,
                "系统核心组件", self.advice.get("system_forbidden", "").format(purpose="系统核心组件"), True)

        # 2) Windows 目录
        if path_l.startswith("c:\\windows"):
            in_temp_sub = any(
                self._startswith_any(path_l, "c:\\windows\\" + s)
                for s in self.win_temp_sub if s != "temp\\*")
            in_temp_sub = in_temp_sub or bool(seg_set & self.temp_keywords)
            if in_temp_sub or ext_l in self.cache_exts:
                return Classification(
                    "temp", 1, "safe", True, "no", False,
                    "Windows 临时/日志文件", self.advice.get("temp_safe", "").format(purpose="Windows 临时或日志文件"), False)
            if ext_l in self.system_exts:
                return Classification(
                    "system", 3, "forbidden", False, "yes", False,
                    "系统核心组件", self.advice.get("system_forbidden", "").format(purpose="系统核心组件"), True)
            return Classification(
                "system", 2, "forbidden", False, "yes", False,
                "Windows 系统文件", self.advice.get("system_no_migrate", "").format(purpose="Windows 系统文件"), True)

        # 3) 回收站
        if "$recycle.bin" in seg_set:
            return Classification(
                "temp", 1, "safe", True, "no", False,
                "回收站内容", "这是回收站中的内容，已由你之前删除过，清空可释放空间，不影响系统。", False)

        # 4) 卸载残留
        for key in self.residue_names:
            if key in name_l:
                return Classification(
                    "app" if "program files" in path_l else "temp",
                    1, "safe", True, "no", True,
                    "软件卸载残留", self.advice.get("residue", "").format(purpose="软件卸载残留"), False)

        # 5) Program Files / ProgramData
        if ("\\program files" in path_l or "\\programdata" in path_l):
            if ext_l in self.cache_exts or bool(seg_set & self.temp_keywords):
                return Classification(
                    "temp", 1, "safe", True, "no", False,
                    "软件缓存/日志", self.advice.get("temp_safe", "").format(purpose="软件运行产生的缓存或日志文件"), False)
            if ext_l in self.installer_exts:
                return Classification(
                    "app", 1, "safe", True, "no", False,
                    "软件安装包", self.advice.get("installer", "").format(purpose="软件安装包或更新包"), False)
            if ext_l in self.system_exts or ext_l in self.app_code_exts:
                return Classification(
                    "app", 2, "forbidden", False, "yes", False,
                    "软件运行必需文件", self.advice.get("system_forbidden", "").format(purpose="软件运行必需文件"), True)
            if is_dir:
                return Classification(
                    "app", 2, "caution", False, "unknown", False,
                    "软件程序目录", "这是已安装软件的程序目录。删除整个文件夹相当于卸载软件，请通过『设置-应用』正常卸载，不要直接删除。", False)
            return Classification(
                "app", 2, "caution", False, "unknown", False,
                "软件数据/配置文件", self.advice.get("app_data", "").format(purpose="软件数据或配置文件"), False)

        # 6) AppData
        if "appdata" in seg_set:
            if self._startswith_any(path_l, self.browser_paths) or \
               bool(seg_set & self.temp_keywords) or ext_l in self.cache_exts:
                return Classification(
                    "temp", 1, "safe", True, "no", False,
                    "应用缓存/临时文件", self.advice.get("temp_safe", "").format(purpose="应用缓存或临时文件"), False)
            if is_dir:
                return Classification(
                    "app", 2, "caution", False, "unknown", False,
                    "应用数据目录", self.advice.get("app_data", "").format(purpose="应用数据目录"), False)
            return Classification(
                "app", 2, "caution", False, "unknown", False,
                "应用数据文件", self.advice.get("app_data", "").format(purpose="应用数据文件"), False)

        # 7) 用户个人目录
        is_user_dir = bool(set(segs[:-1]) & self.user_dirs) if segs else False
        if is_user_dir:
            purp = self._ext_purpose(ext_l) or "文件"
            return Classification(
                "user", 0, "caution", True, "no", False,
                "个人" + purp, self.advice.get("user_caution", "").format(purpose="个人" + purp), False)

        # 8) 空文件夹
        if is_dir and size == 0:
            return Classification(
                "empty", 1, "safe", True, "no", False,
                "空文件夹", self.advice.get("empty_dir", ""), False)

        # 9) 缓存/临时扩展名
        if ext_l in self.cache_exts:
            purp = self.purpose_map.get(ext_l, "临时/缓存文件")
            return Classification(
                "temp", 1, "safe", True, "no", False,
                purp, self.advice.get("temp_safe", "").format(purpose=purp), False)

        # 10) 安装包/压缩包
        if ext_l in self.installer_exts:
            purp = self.purpose_map.get(ext_l, "安装包/压缩包")
            return Classification(
                "user" if is_user_dir else "other",
                0 if is_user_dir else 1,
                "caution", True, "no", False,
                purp, self.advice.get("installer", "").format(purpose=purp), False)

        # 11) 默认
        purp = self._ext_purpose(ext_l)
        if is_dir:
            purp = "文件夹"
            return Classification(
                "other", 0, "caution", True, "unknown", False,
                "普通文件夹", "这是普通文件夹，删除前请先查看里面的内容确认。", False)
        return Classification(
            "other", 0, "caution", True, "unknown", False,
            purp or "其他文件", self.advice.get("unknown", ""), False)

    # ---------- 组装条目 ----------
    def build_entry(self, path: str, name: str, is_dir: bool, ext: str,
                    size: int, ctime: float, drive: str, threshold_mb: int,
                    child_count: int = 0, dir_size: int = 0) -> FileEntry:
        cls = self.classify(path, name, is_dir, ext, size, threshold_mb)
        large = size >= threshold_mb * 1024 * 1024
        advice = cls.advice
        if large:
            hint = self.advice.get("large_hint", "").format(size=self._fmt_mb(size, threshold_mb))
            advice = "【大文件】" + hint + "\n" + advice if hint else advice
        return FileEntry(
            path=path, name=name, is_dir=is_dir, ext=ext,
            size=size, ctime=ctime, drive=drive,
            category=cls.category, risk=cls.risk,
            can_delete=cls.can_delete, can_migrate=cls.can_migrate,
            required=cls.required, residue=cls.residue,
            large=large, purpose=cls.purpose, advice=advice,
            locked=cls.locked, child_count=child_count, dir_size=dir_size,
        )


_FALLBACK_RULES = {
    "whitelist": ["c:\\windows\\system32", "c:\\windows\\syswow64",
                  "c:\\windows\\winsxs", "c:\\program files\\windowsapps",
                  "c:\\boot", "c:\\recovery"],
    "cache_exts": [".tmp", ".log", ".bak", ".old", ".etl", ".blf",
                   ".regtrans-ms", ".cache", ".dmp"],
    "installer_exts": [".msi", ".msu", ".cab", ".iso", ".zip", ".rar",
                       ".7z", ".tar", ".gz"],
    "system_critical_exts": [".dll", ".sys", ".drv", ".mui", ".ocx",
                             ".cpl", ".mof", ".cat", ".efi"],
    "app_code_exts": [".exe", ".com", ".scr", ".bat", ".cmd", ".ps1"],
    "residue_names": ["unins", "$pluginsdir", "installshield",
                      "uninstall", "卸载"],
    "temp_dir_keywords": ["temp", "tmp", "cache", "prefetch", "logs"],
    "windows_temp_subdirs": ["temp", "prefetch", "logs", "cbstemp",
                             "software distribution\\download", "minidump"],
    "browser_cache_paths": ["appdata\\local\\microsoft\\windows\\inetcache",
                            "appdata\\local\\google\\chrome"],
    "user_profile_dirs": ["desktop", "documents", "downloads", "pictures",
                          "music", "videos", "桌面", "文档", "下载", "图片"],
    "user_exts": {"文档类": [".doc", ".docx", ".pdf", ".txt", ".md", ".xls", ".xlsx", ".ppt", ".pptx"],
                  "图片类": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
                  "音视频类": [".mp3", ".mp4", ".mkv", ".avi", ".wav", ".mov"]},
    "purpose_map": {"日志文件": [".log"], "临时文件": [".tmp", ".cache", ".dmp"],
                    "备份文件": [".bak", ".old"], "安装包": [".msi", ".msu", ".cab", ".iso"],
                    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz"],
                    "可执行程序": [".exe", ".com", ".bat", ".cmd"]},
    "advice_templates": {
        "system_forbidden": "这是{purpose}，属于系统或软件运行必需文件。删除会导致系统无法启动或软件损坏，已锁定禁止操作。",
        "system_no_migrate": "这是{purpose}，依赖固定安装位置，迁移会导致系统找不到它，禁止迁移。",
        "temp_safe": "这是{purpose}，属于临时/缓存内容，删除后可释放磁盘空间，不影响正常使用。",
        "residue": "这是{purpose}，疑似软件卸载后残留，确认不再使用后可删除。",
        "installer": "这是{purpose}。已安装完成后可删除以释放空间。",
        "user_caution": "这是{purpose}，属于个人数据。删除前请确认，建议先备份。",
        "app_data": "这是{purpose}，删除可能导致软件设置丢失，建议谨慎处理。",
        "large_hint": "该文件体积较大（{size}），如确认无用可优先清理。",
        "empty_dir": "空文件夹，不占用磁盘空间，可删除。",
        "unknown": "暂无法识别用途，删除前请自行确认。",
    },
}
