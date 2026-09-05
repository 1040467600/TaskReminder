# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 构建配置：dist\TaskReminder\TaskReminder.exe"""
from PyInstaller.utils.hooks import collect_submodules

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
    name='TaskReminder',
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
    name='TaskReminder',
)
