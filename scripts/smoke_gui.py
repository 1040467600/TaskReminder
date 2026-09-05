"""GUI 冒烟验证：offscreen 模式实例化主窗口，遍历所有页面与主题。

用法：python scripts\smoke_gui.py
自动设置 QT_QPA_PLATFORM=offscreen（无显示环境）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = str(ROOT / ".tmp_test" / "smoke_appdata")

from PyQt6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    from task_reminder.ui import theme
    from task_reminder.ui.main_window import MainWindow

    app = QApplication(sys.argv)

    for mode in ("light", "dark"):
        theme.apply_theme(app, mode, 13)
        win = MainWindow()
        win.resize(1200, 800)
        win.show()
        app.processEvents()

        visited = []
        for key, btn in win._nav_buttons.items():
            btn.click()
            app.processEvents()
            visited.append(key)

        assert visited == ["tasks", "dashboard", "history", "settings"], visited
        assert win.stack.currentIndex() == 3
        print(f"[{mode}] pages visited: {visited}; rows on tasks page: {win.tasks_page.model.rowCount()}")
        win.close()
        app.processEvents()

    print("GUI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
