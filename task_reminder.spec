# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 构建配置：dist\\彭城派出所任务闭环管理系统\\彭城派出所任务闭环管理系统.exe"""
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = '彭城派出所任务闭环管理系统'

hidden = collect_submodules('PyQt6.QtMultimedia')

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('task_reminder\\assets', 'assets')],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    version='build\\version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
