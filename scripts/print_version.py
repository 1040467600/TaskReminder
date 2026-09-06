# -*- coding: utf-8 -*-
"""输出应用版本号（供 build_windows.ps1 调用，避免 -c 引号转义问题）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from task_reminder import __version__  # noqa: E402

print(__version__)
