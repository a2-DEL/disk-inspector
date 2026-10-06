# -*- coding: utf-8 -*-
"""文件占用（锁定）检测与磁盘空间查询，全部基于 ctypes，无额外依赖。"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Optional

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_SHARING_VIOLATION = 32
ERROR_ACCESS_DENIED = 5

_kernel32 = ctypes.windll.kernel32
_CreateFileW = _kernel32.CreateFileW
_CreateFileW.restype = wintypes.HANDLE
_CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_CloseHandle = _kernel32.CloseHandle
_GetLastError = _kernel32.GetLastError


def is_locked(path: str) -> Optional[bool]:
    """检测文件是否被其他进程占用（无法独占访问）。

    返回 True=占用中 / False=未被占用 / None=权限不足无法判断。
    """
    if not os.path.exists(path):
        return None
    # 以“拒绝共享”方式打开，若其他进程已以不兼容共享模式占用则失败
    handle = _CreateFileW(
        path,
        GENERIC_READ,
        0,  # 不共享：任何其他打开都会导致本调用失败；本调用也会暂时锁定文件
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle and handle != INVALID_HANDLE_VALUE:
        _CloseHandle(handle)
        return False
    err = _GetLastError()
    if err == ERROR_ACCESS_DENIED:
        return None
    if err == ERROR_SHARING_VIOLATION or err == 32:
        return True
    # 其他错误（如文件正被独占删除）视为占用
    return True


def disk_usage(drive: str) -> Optional[dict]:
    """获取盘符剩余/总空间。drive 形如 'C:\\'。返回 dict 或 None。"""
    try:
        free = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        avail = ctypes.c_ulonglong(0)
        ok = _kernel32.GetDiskFreeSpaceExW(
            drive, ctypes.byref(avail), ctypes.byref(total), ctypes.byref(free))
        if not ok:
            return None
        return {"total": total.value, "free": free.value,
                "used": total.value - free.value}
    except Exception:
        return None


def file_attributes(path: str) -> Optional[int]:
    try:
        return _kernel32.GetFileAttributesW(path)
    except Exception:
        return None


FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_DIRECTORY = 0x10


def is_hidden_or_system(path: str) -> tuple:
    """返回 (is_hidden, is_system)。"""
    attrs = file_attributes(path)
    if attrs is None or attrs == -1:
        return False, False
    return bool(attrs & FILE_ATTRIBUTE_HIDDEN), bool(attrs & FILE_ATTRIBUTE_SYSTEM)
