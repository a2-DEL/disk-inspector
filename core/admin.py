# -*- coding: utf-8 -*-
"""管理员权限检测与重新以管理员身份启动。"""
from __future__ import annotations

import ctypes
import os
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(elevated_arg: str = "--elevated") -> bool:
    """以管理员权限重新启动当前程序。成功返回 True，用户取消返回 False。"""
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = ""
        else:
            exe = sys.executable
            params = f'"{os.path.abspath(sys.argv[0])}" {elevated_arg}'
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, None, 1)
        return ret > 32
    except Exception:
        return False
