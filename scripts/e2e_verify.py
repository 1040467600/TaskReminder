"""E2E 验证构建产物：onedir/onefile 启动 + 安装包静默安装/卸载。

用法：python scripts\\e2e_verify.py [--skip-install]
前置：已运行 scripts\\build_windows.ps1 生成 dist 下产物。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
INST_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "TaskReminder"


def run(cmd, **kw):
    print(f"$ {cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))}")
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check_startup(exe: Path, name: str) -> bool:
    """启动 exe，5 秒后检查进程存活（GUI 已初始化），再结束。"""
    if not exe.exists():
        print(f"[FAIL] {name}: {exe} 不存在")
        return False
    proc = subprocess.Popen([str(exe)])
    time.sleep(5)
    alive = proc.poll() is None
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print(f"[PASS] {name} 启动并稳定运行 5s（pid 正常退出）")
    else:
        print(f"[FAIL] {name} 启动后立即退出，code={proc.returncode}")
    return alive


def main() -> int:
    ok = True

    ok &= check_startup(DIST / "TaskReminder" / "TaskReminder.exe", "onedir 主程序")
    ok &= check_startup(DIST / "TaskReminder.exe", "onefile 便携版")

    setup = DIST / "TaskReminderSetup.exe"
    if INST_DIR.exists():
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(INST_DIR)], capture_output=True)

    print("== 静默安装 ==")
    r = run([str(setup), "/S"])
    time.sleep(2)
    installed = INST_DIR / "TaskReminder.exe"
    if installed.exists():
        print(f"[PASS] 静默安装完成：{installed}")
    else:
        print(f"[FAIL] 静默安装后未找到 {installed}；stdout={r.stdout[-200:] if r.stdout else ''}")
        ok = False

    if installed.exists():
        ok &= check_startup(installed, "安装版程序")

        print("== 静默卸载 ==")
        run([str(INST_DIR / "uninstall.exe"), "--uninstall"])
        time.sleep(3)
        if not installed.exists():
            print("[PASS] 静默卸载完成（程序文件已清理）")
        else:
            print("[FAIL] 卸载后文件仍存在")
            ok = False

    print("\nE2E RESULT:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
