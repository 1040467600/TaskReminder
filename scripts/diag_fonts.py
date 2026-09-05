"""诊断 Qt 字体加载：列出可用字体家族，检测 CJK 支持。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
fams = QFontDatabase.families()
print("total families:", len(fams))
cjk = [f for f in fams if any(k in f for k in ("YaHei", "SimSun", "SimHei", "微软", "宋体", "黑体", "Noto Sans CJK", "PingFang"))]
print("cjk families:", cjk[:10])
print("sample:", fams[:15])
