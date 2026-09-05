"""应用入口：初始化 QApplication、主题、单实例锁并启动主窗口。"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, __version__, app_config
from . import db


def _single_instance_key() -> str:
    return f"TaskReminder-{__version__}"


def _is_another_running() -> tuple[bool, QLocalServer | None]:
    client = QLocalSocket()
    client.connectToServer(_single_instance_key())
    if client.waitForConnected(300):
        client.disconnectFromServer()
        return True, None
    server = QLocalServer()
    QLocalServer.removeServer(_single_instance_key())
    server.listen(_single_instance_key())
    return False, server


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("TaskReminder")
    app.setApplicationVersion(__version__)

    another, server = _is_another_running()
    if another:
        QMessageBox.information(None, APP_NAME, "任务提醒助手已在运行中（请查看系统托盘）。")
        return 0
    app.aboutToQuit.connect(server.close if server else (lambda: None))

    # 初始化数据库（默认 %APPDATA%/TaskReminder/tasks.db）
    db.init()

    from .ui.theme import apply_theme
    theme_name = app_config.get("theme", "light")
    font_size = int(app_config.get("font_size", 13))
    apply_theme(app, theme_name, font_size)

    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()

    # 关闭窗口后不因托盘存在而退出
    app.setQuitOnLastWindowClosed(False)

    def on_last_closed():
        pass

    rc = app.exec()
    db.close()
    return rc


if __name__ == "__main__":
    sys.exit(run())
