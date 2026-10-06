# -*- coding: utf-8 -*-
"""集成测试：小范围扫描 → 分类 → HTML 报告 → 文件操作（备份/迁移/回收站）。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from core.config import AppConfig
from core.scanner import scan
from core.report import generate_html, fmt_size
from core import fileops

FIX = os.path.join(BASE, "_testfix")


def build_fixture():
    if os.path.exists(FIX):
        shutil.rmtree(FIX, ignore_errors=True)
    mk = lambda *p: (os.makedirs(os.path.join(FIX, *p), exist_ok=True),
                     os.path.join(FIX, *p))[1]
    mk("Program Files", "MyApp")
    mk("AppData", "Local", "Temp")
    mk("Documents")
    mk("Downloads")
    mk("EmptyFolder")
    open(os.path.join(mk("Program Files", "MyApp"), "app.exe"), "wb").write(b"MZ" + b"\0" * 4000)
    open(os.path.join(mk("Program Files", "MyApp"), "app.dll"), "wb").write(b"\0" * 3000)
    open(os.path.join(mk("Program Files", "MyApp"), "app.log"), "wb").write(b"log line\n" * 100)
    open(os.path.join(mk("Program Files", "MyApp"), "unins000.exe"), "wb").write(b"unins" * 800)
    open(os.path.join(mk("AppData", "Local", "Temp"), "junk.tmp"), "wb").write(b"junk" * 1000)
    open(os.path.join(mk("Documents"), "报告.docx"), "wb").write(b"doc" * 2000)
    open(os.path.join(mk("Documents"), "photo.jpg"), "wb").write(b"jpg" * 1500)
    open(os.path.join(mk("Downloads"), "setup.zip"), "wb").write(b"zip" * 3000)
    # 大文件 12MB，阈值设 10MB
    big = os.path.join(mk("Downloads"), "big_video.mp4")
    with open(big, "wb") as f:
        f.write(b"\0" * (12 * 1024 * 1024))
    print(f"fixture: {FIX}")


def main():
    build_fixture()
    cfg = AppConfig()
    cfg.large_threshold_mb = 10
    cfg.check_occupied = True

    print("=== 1) 扫描（deep，含占用检测）===")
    res = scan([FIX], cfg, "deep")
    print(f"文件 {res.stats['files']} 个，目录 {res.stats['dirs']} 个，"
          f"容量 {fmt_size(res.stats['size'])}，大文件 {res.stats['large']}，"
          f"可清理 {res.stats['junk']}，锁定 {res.stats['locked']}")
    res.build_index()

    print("\n=== 2) 分类抽查 ===")
    for e in res.entries:
        if e.is_dir:
            continue
        print(f"  [{e.category}/{e.risk_label}] {e.name}: 必需={e.required_label} "
              f"可删={e.can_delete_label} 迁移={'可' if e.can_migrate else '不可'} "
              f"残留={'是' if e.residue else '否'} 大={'是' if e.large else '否'} | {e.purpose} | {e.advice[:40]}")

    assert any(e.name == "app.dll" and e.locked for e in res.entries if not e.is_dir), "app.dll 应锁定"
    assert any(e.name == "junk.tmp" and e.category == "temp" and e.can_delete == "safe" for e in res.entries), "tmp 应为临时可删"
    assert any(e.name == "unins000.exe" and e.residue for e in res.entries), "unins 应标残留"
    assert any(e.name == "big_video.mp4" and e.large for e in res.entries), "大文件应标记"
    assert any(e.name == "报告.docx" and e.category == "user" for e in res.entries), "文档应为用户文件"
    assert any(e.name == "EmptyFolder" and e.is_dir and e.category == "empty" for e in res.entries), "空文件夹归类"
    assert any(e.name == "setup.zip" and e.category == "user" for e in res.entries), "下载安装包应为用户文件"
    print("  分类断言全部通过 ✓")

    print("\n=== 3) HTML 报告生成 ===")
    out = os.path.join(BASE, "test_report.html")
    generate_html(res, cfg, out)
    size = os.path.getsize(out)
    with open(out, "r", encoding="utf-8") as f:
        content = f.read()
    assert "磁盘文件检视报告" in content and "var DATA" in content, "HTML 关键内容缺失"
    assert "big_video.mp4" in content and "unins000.exe" in content
    print(f"  HTML 已生成：{out}（{size // 1024} KB），关键内容校验通过 ✓")

    print("\n=== 4) 文件操作 ===")
    # 备份
    bak_root = os.path.join(tempfile.gettempdir(), "disk_inspector_bak")
    items = [{"path": os.path.join(FIX, "Documents", "报告.docx"), "size": 0}]
    r = fileops.run_batch(items, "backup", {"dest": bak_root})
    assert r[0]["ok"], f"备份失败: {r[0]['msg']}"
    print(f"  备份 ✓ {r[0]['msg']}")
    # 迁移（保留原文件）
    mig_root = os.path.join(tempfile.gettempdir(), "disk_inspector_mig")
    items = [{"path": os.path.join(FIX, "Documents", "photo.jpg"), "size": 0}]
    r = fileops.run_batch(items, "migrate", {"dest": mig_root, "delete_original": False})
    assert r[0]["ok"], f"迁移失败: {r[0]['msg']}"
    assert os.path.exists(os.path.join(FIX, "Documents", "photo.jpg")), "原文件应保留"
    print(f"  迁移 ✓ {r[0]['msg']}")
    # 移入回收站（测试垃圾文件）
    junk = os.path.join(FIX, "AppData", "Local", "Temp", "junk.tmp")
    items = [{"path": junk, "size": 0}]
    r = fileops.run_batch(items, "delete_recycle", {})
    print(f"  回收站删除 ✓（返回：{r[0]['msg'] or '成功'}）" if r[0]["ok"] else f"  回收站删除失败: {r[0]['msg']}")
    # 彻底删除 + 还原
    perm = os.path.join(FIX, "Downloads", "setup.zip")
    items = [{"path": perm, "size": 0}]
    r = fileops.run_batch(items, "delete_permanent", {})
    assert r[0]["ok"] and r[0]["msg"].find("安全回收箱") >= 0, f"彻底删除失败: {r[0]}"
    tp = r[0]["msg"].split("->")[-1].strip()
    assert os.path.exists(tp), f"回收箱路径不存在: {tp}"
    print(f"  彻底删除 ✓ {r[0]['msg']}")
    rr = fileops.run_batch([{"path": tp}], "restore",
                           {"trash_path": tp, "original": perm})
    assert rr[0]["ok"], f"还原失败: {rr[0]}"
    assert os.path.exists(perm), "还原后文件应存在"
    print(f"  还原 ✓ {perm}")
    print("  文件操作全部通过 ✓")

    print("\n✅ 集成测试全部通过")


if __name__ == "__main__":
    main()
