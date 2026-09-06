"""GUI 截图：启动主窗口，抓取各页面与对话框存为 PNG（供用户手册使用）。

用法：python scripts\\capture_screens.py

渲染说明：offscreen 平台走 freetype，QT_QPA_FONTDIR 指向系统字体目录，
绕开沙箱内 DirectWrite 初始化失败导致的中文方块问题。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = "C:\\Windows\\Fonts"
os.environ["APPDATA"] = str(ROOT / ".tmp_test" / "smoke_appdata")

IMG_DIR = ROOT / "docs" / "images"


def main() -> int:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    from task_reminder import db, repository as repo
    from task_reminder.models import fmt
    from task_reminder.ui import theme
    from task_reminder.ui.main_window import MainWindow
    from task_reminder.ui.task_dialog import TaskDialog

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_Use96Dpi, True)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    db.init()
    # 造演示数据
    if not repo.all_tasks():
        now = datetime.now()
        repo.add_task("编写季度总结报告", "张伟", "汇总 Q3 各部门数据并撰写报告。",
                      fmt(now + timedelta(days=3)), fmt(now + timedelta(days=3, hours=-1)))
        repo.add_task("客户系统巡检", "李娜", "完成客户环境月度巡检并提交巡检单。",
                      fmt(now + timedelta(days=1)), fmt(now + timedelta(hours=12)),
                      status="进行中")
        repo.add_task("归档合同文件", "王强", "纸质合同扫描归档。",
                      fmt(now - timedelta(days=1)), fmt(now - timedelta(days=1, hours=2)),
                      status="已完成")

    theme.apply_theme(app, "light", 13)
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    app.processEvents()

    def shot(widget, name):
        app.processEvents()
        widget.grab().save(str(IMG_DIR / name))
        print(f"saved {name}")

    shot(win, "tasks_page.png")

    for i, name in ((1, "dashboard_page.png"), (2, "history_page.png"), (3, "settings_page.png")):
        win._switch_page(i)
        app.processEvents()
        shot(win, name)

    win._switch_page(0)
    dlg = TaskDialog()
    dlg.resize(720, 640)
    dlg.show()
    app.processEvents()
    shot(dlg, "task_dialog.png")
    dlg.close()

    # 深色主题对比图
    theme.apply_theme(app, "dark", 13)
    win._apply_theme("dark", 13)
    app.processEvents()
    shot(win, "tasks_page_dark.png")

    win.close()
    print("screens captured ->", IMG_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
