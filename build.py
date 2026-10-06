# -*- coding: utf-8 -*-
"""打包脚本：生成图标 → PyInstaller 打包单文件 EXE → 创建桌面快捷方式。

用法：
    py -3.13 build.py
"""
from __future__ import annotations

import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "磁盘文件检视工具"


def make_icon(path: str) -> str:
    """用 PyQt 绘制一个文件夹+放大镜图标并保存为 .ico。"""
    from PyQt6.QtCore import Qt, QRectF
    from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
    size = 256
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # 圆角底色
    p.setBrush(QColor("#2D7FF9"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(8, 8, size - 16, size - 16, 48, 48)
    # 文件夹
    p.setBrush(QColor("#FFC247"))
    p.drawRoundedRect(40, 78, 176, 118, 14, 14)
    p.setBrush(QColor("#FFD985"))
    p.drawRoundedRect(40, 70, 96, 30, 12, 12)
    # 放大镜
    p.setBrush(QColor("#FFFFFF"))
    p.setPen(QPen(QColor("#FFFFFF"), 14))
    p.drawEllipse(QRectF(92, 130, 62, 62))
    p.setPen(QPen(QColor("#2D7FF9"), 16, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(143, 182, 178, 217)
    p.end()
    img.save(path, "ICO")
    return path


def build() -> None:
    print("[1/3] 生成图标…")
    icon = make_icon(os.path.join(BASE, "icon.ico"))
    print(f"       图标：{icon}")

    print("[2/3] PyInstaller 打包单文件 EXE（首次约需 2-5 分钟）…")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", APP_NAME,
        "--icon", icon,
        "--add-data", os.path.join("config", "rules.json") + os.pathsep + "config",
        "--hidden-import", "PyQt6.QtSvg",
        os.path.join(BASE, "main.py"),
    ]
    r = subprocess.run(cmd, cwd=BASE)
    if r.returncode != 0:
        print("❌ 打包失败，请查看上方错误信息。")
        sys.exit(1)
    exe = os.path.join(BASE, "dist", APP_NAME + ".exe")
    print(f"       EXE 已生成：{exe}")

    print("[3/3] 创建桌面快捷方式…")
    lnk = os.path.join(os.path.expanduser("~"), "Desktop", APP_NAME + ".lnk")
    ps = (
        "$ws = New-Object -ComObject WScript.Shell;"
        f"$s = $ws.CreateShortcut('{lnk}');"
        f"$s.TargetPath = '{exe}';"
        f"$s.WorkingDirectory = '{os.path.dirname(exe)}';"
        f"$s.IconLocation = '{exe},0';"
        "$s.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       check=True, capture_output=True, timeout=30)
        print(f"       快捷方式：{lnk}")
    except Exception as e:
        print(f"⚠️ 快捷方式创建失败：{e}（可稍后在工具「设置」中手动创建）")

    print("✅ 全部完成！双击桌面快捷方式即可运行。")


if __name__ == "__main__":
    build()
