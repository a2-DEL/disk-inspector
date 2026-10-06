import ctypes, os, shutil, sys, time, threading
sys.path.insert(0, os.getcwd())
# 1) 构造 12000 层超深目录
base = r"D:\di_deep_test"
if os.path.exists(base):
    def iter_remove(top):
        stack, dirs = [top], []
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(os.path.join(d, e.name))
                        else:
                            try: os.remove(os.path.join(d, e.name))
                            except OSError: pass
            except OSError: pass
            dirs.append(d)
        for d in reversed(dirs):
            try: os.rmdir(d)
            except OSError: pass
    iter_remove(base)
os.makedirs(base)
k32 = ctypes.windll.kernel32
cur = "\\\\?\\" + base
ok = 0
for i in range(12000):
    cur += r"\a"
    if k32.CreateDirectoryW(cur, None):
        ok += 1
print("created layers:", ok, "path_len:", len(cur))

# 2) 修复版迭代扫描计时（线程模拟 QThread 1MB 栈）
from core.config import AppConfig
from core.scanner import scan
result = {}
def run():
    try:
        t0 = time.time()
        res = scan([r"\\?\D:\di_deep_test"], AppConfig(), "deep")
        result.update(dirs=res.stats["dirs"], files=res.stats["files"], sec=round(time.time()-t0, 1))
    except BaseException as e:
        result["exc"] = repr(e)
t = threading.Thread(target=run); t.start(); t.join(timeout=300)
alive = t.is_alive()
print("RESULT:", result, "THREAD_ALIVE_AFTER_TIMEOUT:", alive)
print("PROCESS_SURVIVED")
