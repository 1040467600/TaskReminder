"""应用入口：初始化 QApplication、主题、单实例锁并启动主窗口。"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, __version__, app_config
from . import db


def _setup_logging() -> None:
    """文件日志（%APPDATA%/TaskReminder/logs/app.log，单文件 1MB×3）。

    轮询异常、数据库重连等问题现场需要可追溯，避免"几天后才发现不提醒"
    却无任何日志可查。
    """
    log_dir = Path(db.default_db_path()).parent / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000,
                                      backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
    except OSError:
        pass  # 日志不可用时不影响主程序


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

    # 窗口/任务栏图标（所有对话框继承）
    from .notifier import app_icon
    app.setWindowIcon(app_icon())

    another, server = _is_another_running()
    if another:
        QMessageBox.information(None, APP_NAME, "任务提醒助手已在运行中（请查看系统托盘）。")
        return 0
    app.aboutToQuit.connect(server.close if server else (lambda: None))

    # 初始化数据库（默认 %APPDATA%/TaskReminder/tasks.db）
    _setup_logging()
    logging.getLogger("task_reminder").info("应用启动 v%s", __version__)

    # 全局未捕获异常落日志（windowed 打包后 stderr 不可见，否则闪退无现场）
    def _excepthook(exc_type, exc, tb):
        logging.getLogger("task_reminder").error(
            "未捕获异常", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = _excepthook

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
