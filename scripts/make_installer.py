"""TaskReminder 自包含安装器。

本脚本由 PyInstaller 打包为 dist\\TaskReminderSetup.exe（onefile, windowed），
payload zip 通过 --add-data 嵌入。支持：
- GUI 向导：选择安装目录、创建桌面/开始菜单快捷方式
- /S        静默安装（默认目录 %LOCALAPPDATA%\\Programs\\TaskReminder）
- --uninstall  静默卸载（读取注册表 InstallLocation）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import winreg
import zipfile
from pathlib import Path

APP_NAME = "TaskReminder"
DISPLAY_NAME = "任务提醒助手"
PUBLISHER = "TaskReminder Project"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TaskReminder"
SILENT_FLAGS = ("/S", "-S", "/s")


def resource(rel: str) -> Path:
    """定位随包资源（PyInstaller 下在 _MEIPASS，源码模式下回退仓库路径）。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return Path(__file__).resolve().parent.parent / rel


def payload_zip() -> Path:
    p = resource("payload/installer_payload.zip")
    if not p.exists():  # onefile 打包时 add-data 平铺在 _MEIPASS 根
        p = resource("installer_payload.zip")
    return p


def read_version() -> str:
    vf = resource("app_version.txt")
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return "1.0.0"


def default_install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME


def desktop_dir() -> Path:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    d = out.stdout.strip()
    return Path(d) if d else Path.home() / "Desktop"


def create_shortcut(lnk: Path, target: Path):
    ps = (
        f"$ws = New-Object -ComObject WScript.Shell;"
        f"$s = $ws.CreateShortcut('{lnk}');"
        f"$s.TargetPath = '{target}';"
        f"$s.WorkingDirectory = '{target.parent}';"
        f"$s.IconLocation = '{target},0';"
        f"$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def remove_shortcut(lnk: Path):
    try:
        if lnk.exists():
            lnk.unlink()
    except OSError:
        pass


def write_registry(install_dir: Path, version: str):
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
    with key:
        size_kb = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file()) // 1024
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, DISPLAY_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(install_dir / f"{APP_NAME}.exe"))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                          f'"{install_dir / "uninstall.exe"}" --uninstall')
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ,
                          f'"{install_dir / "uninstall.exe"}" --uninstall')
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def delete_registry():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except FileNotFoundError:
        pass


def install(install_dir: Path, desktop: bool, start_menu: bool, log) -> None:
    log(f"安装目录: {install_dir}")
    install_dir.mkdir(parents=True, exist_ok=True)

    log("解压程序文件 ...")
    with zipfile.ZipFile(payload_zip()) as z:
        z.extractall(install_dir)

    version = read_version()
    log("写入卸载信息 ...")
    write_registry(install_dir, version)

    me = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    try:
        shutil.copy2(me, install_dir / "uninstall.exe")
    except OSError:
        pass

    exe = install_dir / f"{APP_NAME}.exe"
    if start_menu:
        sm_dir = (Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs" / DISPLAY_NAME)
        sm_dir.mkdir(parents=True, exist_ok=True)
        create_shortcut(sm_dir / f"{DISPLAY_NAME}.lnk", exe)
        log("已创建开始菜单快捷方式")
    if desktop:
        create_shortcut(desktop_dir() / f"{DISPLAY_NAME}.lnk", exe)
        log("已创建桌面快捷方式")
    log("安装完成。")


def uninstall(log) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            loc, _ = winreg.QueryValueEx(k, "InstallLocation")
        target = Path(loc)
    except FileNotFoundError:
        target = default_install_dir()
    log(f"卸载目录: {target}")

    delete_registry()
    remove_shortcut(desktop_dir() / f"{DISPLAY_NAME}.lnk")
    sm_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs" / DISPLAY_NAME
    if sm_dir.exists():
        shutil.rmtree(sm_dir, ignore_errors=True)

    if target.exists():
        for f in target.rglob("*"):
            try:
                if f.is_file() or f.is_symlink():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
            except OSError:
                pass
        # 自删：延迟数秒待 uninstall.exe 退出后删除残留
        subprocess.Popen(
            ["cmd", "/c", "ping", "-n", "6", "127.0.0.1", ">nul", "&",
             "rd", "/s", "/q", str(target)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    log("卸载完成。")


# ---------------------------------------------------------------------------
# GUI
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"{DISPLAY_NAME} 安装向导")
    root.geometry("560x360")
    root.resizable(False, False)

    ver = read_version()
    tk.Label(root, text=f"{DISPLAY_NAME} v{ver}", font=("Microsoft YaHei UI", 15, "bold")).pack(pady=(18, 4))
    tk.Label(root, text="单机版任务提醒软件 · 本地存储 · 无需联网", fg="#555").pack()

    row = tk.Frame(root)
    row.pack(pady=(18, 4), padx=24, fill="x")
    tk.Label(row, text="安装到：").pack(side="left")
    var_dir = tk.StringVar(value=str(default_install_dir()))
    ent = tk.Entry(row, textvariable=var_dir)
    ent.pack(side="left", fill="x", expand=True, padx=6)

    def browse():
        d = filedialog.askdirectory(initialdir=var_dir.get())
        if d:
            var_dir.set(d)
    tk.Button(row, text="浏览...", command=browse).pack(side="left")

    var_desktop = tk.BooleanVar(value=True)
    var_sm = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="创建桌面快捷方式", variable=var_desktop).pack(anchor="w", padx=40)
    tk.Checkbutton(root, text="创建开始菜单快捷方式", variable=var_sm).pack(anchor="w", padx=40)

    bar = ttk.Progressbar(root, mode="indeterminate", length=480)
    txt = tk.Text(root, height=6, state="disabled", bg="#f5f5f5", relief="flat")

    def log(msg: str):
        txt.configure(state="normal")
        txt.insert("end", msg + "\n")
        txt.see("end")
        txt.configure(state="disabled")

    def do_install(btn):
        btn.configure(state="disabled")
        bar.pack(pady=6)
        bar.start(12)
        txt.pack(padx=24, fill="both", expand=True)

        def work():
            try:
                install(Path(var_dir.get()), var_desktop.get(), var_sm.get(), log)
            except Exception as e:  # noqa: BLE001
                root.after(0, lambda: messagebox.showerror("安装失败", str(e)))
                root.after(0, lambda: (bar.stop(), bar.pack_forget(), btn.configure(state="normal")))
                return
            bar.stop()
            root.after(0, lambda: messagebox.showinfo("安装完成", f"{DISPLAY_NAME} v{ver} 已安装到：\n{var_dir.get()}"))
            root.after(200, root.destroy)

        threading.Thread(target=work, daemon=True).start()

    btn_install = tk.Button(root, text="安装", width=14, bg="#2563EB", fg="white",
                            activebackground="#1E40AF", activeforeground="white")
    btn_install.configure(command=lambda: do_install(btn_install))
    btn_install.pack(pady=10)

    root.mainloop()


def main() -> int:
    argv = sys.argv[1:]
    if "--uninstall" in argv:
        uninstall(print)
        return 0
    if any(a in SILENT_FLAGS for a in argv):
        install(default_install_dir(), True, True, print)
        return 0
    run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
