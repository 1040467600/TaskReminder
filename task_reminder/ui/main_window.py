"""主窗口：侧边栏导航（任务管理 / 数据看板 / 提醒历史 / 设置）+ 托盘。"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenu, QStackedWidget,
                             QSystemTrayIcon, QVBoxLayout, QWidget, QPushButton,
                             QButtonGroup, QHBoxLayout, QFrame)

from .. import APP_NAME, __version__, app_config, db, repository
from ..models import TaskStatus
from ..reminder_service import ReminderService
from . import theme
from .dashboard_page import DashboardPage
from .history_page import HistoryPage
from ..notifier import Notifier, app_icon
from .settings_page import SettingsPage
from .tasks_page import TasksPage

PAGES = [
    ("tasks", "📋 任务管理"),
    ("dashboard", "📊 数据看板"),
    ("history", "🔔 提醒历史"),
    ("settings", "⚙️ 设置"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setMinimumSize(800, 600)
        self._restore_window_state()
        self.service = ReminderService(self)
        self.notifier = Notifier(self)
        self._build()
        self._build_tray()
        self._wire()

    # ------------------------------------------------------------------
    def _build(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边栏
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(10, 0, 10, 10)
        sv.setSpacing(4)
        title = QLabel("任务提醒助手")
        title.setObjectName("appTitle")
        sv.addWidget(title)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons = {}
        for i, (key, text) in enumerate(PAGES):
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav_group.addButton(btn, i)
            sv.addWidget(btn)
            self._nav_buttons[key] = btn
        self._nav_group.idClicked.connect(self._switch_page)
        sv.addStretch(1)
        ver = QLabel(f"版本 v{__version__}")
        ver.setObjectName("appVersion")
        sv.addWidget(ver)
        root.addWidget(sidebar)

        # 页面栈
        self.stack = QStackedWidget()
        self.tasks_page = TasksPage()
        self.dashboard_page = DashboardPage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage()
        for w in (self.tasks_page, self.dashboard_page, self.history_page, self.settings_page):
            self.stack.addWidget(w)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._nav_buttons["tasks"].setChecked(True)
        self.stack.setCurrentIndex(0)

        # 状态栏
        self.status_db = QLabel("")
        self.status_sort = QLabel("")
        self.status_next = QLabel("")
        sb = self.statusBar()
        sb.addWidget(self.status_db)
        sb.addWidget(self.status_sort)
        sb.addPermanentWidget(self.status_next)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        key = PAGES[idx][0]
        if key == "dashboard":
            self.dashboard_page.refresh()
        elif key == "history":
            self.history_page.refresh()
        elif key == "tasks":
            self.tasks_page.refresh()
            self.status_sort.setText(f"　排序：{self.tasks_page.current_sort_text()}")

    # ------------------------------------------------------------------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("任务提醒助手")
        menu = QMenu()
        act_show = QAction("显示主窗口", self)
        act_quit = QAction("退出", self)
        act_show.triggered.connect(self._show_normal)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._show_normal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        app_config.set("window_state", self._window_state_json())
        self.service.stop()
        QApplication.quit()

    # ------------------------------------------------------------------
    def _wire(self):
        self.service.task_due.connect(self._on_task_due)
        self.notifier.queue_changed.connect(self._update_next_status)
        self.tasks_page.data_changed.connect(self.dashboard_page.refresh)
        self.settings_page.theme_changed.connect(self._apply_theme)
        self.service.start()
        QTimer.singleShot(0, self.notifier.pump)

        # 状态栏刷新定时器（30s）
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(30_000)
        self._status_timer.timeout.connect(self._update_next_status)
        self._status_timer.start()
        self._update_next_status()

    def _on_task_due(self, task, history_id):
        self.notifier.notify(task, history_id)
        QTimer.singleShot(0, self.notifier.pump)
        if self.stack.currentIndex() in (0, 1):
            self.tasks_page.refresh()
            self.dashboard_page.refresh()

    def _apply_theme(self, theme_name: str, font_size: int):
        theme.apply_theme(QApplication.instance(), theme_name, font_size)

    def _update_next_status(self):
        self.status_db.setText(f"数据目录：{db.db_path()}")
        self.status_sort.setText(f"　排序：{self.tasks_page.current_sort_text()}")
        due_count = len(repository.due_for_reminder()) + self.notifier.pending_count()
        self.status_next.setText(f"轮询 {int(app_config.get('poll_interval', 5))}s　待处理提醒 {due_count}")

    # ------------------------------------------------------------------
    def _window_state_json(self) -> str:
        import json
        g = self.geometry()
        return json.dumps({"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height(),
                           "maximized": self.isMaximized()})

    def _restore_window_state(self):
        import json
        raw = app_config.get("window_state", "")
        if raw:
            try:
                s = json.loads(raw)
                self.setGeometry(s.get("x", 120), s.get("y", 120),
                                 max(800, s.get("w", 1000)), max(600, s.get("h", 680)))
                if s.get("maximized"):
                    self.setWindowState(Qt.WindowState.WindowMaximized)
                return
            except (ValueError, TypeError):
                pass
        self.resize(1000, 680)

    # ------------------------------------------------------------------
    def closeEvent(self, ev):
        if bool(app_config.get("tray_close", True)):
            ev.ignore()
            self.hide()
            self.tray.showMessage("任务提醒助手", "已最小化到托盘，双击托盘图标可再次打开。",
                                  QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            app_config.set("window_state", self._window_state_json())
            self.service.stop()
            ev.accept()
