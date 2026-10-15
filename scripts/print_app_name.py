"""打印 EXE 基础名（不含 .exe），供 build_windows.ps1 捕获使用。

保持 ps1 脚本纯 ASCII，避免 PowerShell 5.1 对无 BOM 中文脚本的编码误判。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_reminder import APP_NAME

print(APP_NAME)
