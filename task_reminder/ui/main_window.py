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
        # 标题行：应用图标 + 名称
        head = QHBoxLayout()
        head.setContentsMargins(4, 16, 0, 6)
        head.setSpacing(8)
        icon_lbl = QLabel()
        pm = app_icon().pixmap(26, 26)
        if not pm.isNull():
            icon_lbl.setPixmap(pm)
        title = QLabel("任务提醒助手")
        title.setObjectName("appTitle")
        head.addWidget(icon_lbl)
        head.addWidget(title)
        head.addStretch(1)
        sv.addLayout(head)
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
        elif key == "settings":
            # 设置页的已保存搜索列表与任务页搜索栏保持同步
            self.settings_page.reload_searches()

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
        # 让通知器持有托盘引用，后台触发时才能弹出系统气泡
        self.notifier.setup_tray(self.tray)

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
        self.notifier.responded.connect(self._on_reminder_responded)
        self.tasks_page.data_changed.connect(self.dashboard_page.refresh)
        self.tasks_page.data_changed.connect(self._update_next_status)
        # 任务页分页菜单改每页条数 → 同步设置页下拉框显示
        self.tasks_page.pager.page_size_changed.connect(self._sync_settings_page_size)
        self.settings_page.theme_changed.connect(self._apply_theme)
        # 设置页改动立即生效（轮询间隔/每页条数），无需重启
        self.settings_page.behavior_changed.connect(self._on_behavior_changed)
        # 恢复备份后立即刷新所有页面
        self.settings_page.data_restored.connect(self._on_data_restored)
        # 设置页删除已保存搜索 → 同步任务页搜索栏下拉框
        self.settings_page.searches_changed.connect(self.tasks_page.search.reload_saved_searches)
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
        # 提醒一旦触发，立即刷新任务表/看板/历史，避免用户看到滞后数据
        self.tasks_page.refresh()
        self.dashboard_page.refresh()
        self.history_page.refresh()

    def _on_reminder_responded(self, response: str):
        """弹窗响应（稍后提醒/标记完成/关闭）后立即刷新所有页面数据。"""
        self.tasks_page.refresh()
        self.dashboard_page.refresh()
        self.history_page.refresh()
        self._update_next_status()

    def _on_behavior_changed(self):
        """设置页行为改动立即应用：轮询间隔 + 每页条数。"""
        self.service.apply_interval()
        self.tasks_page.sync_page_size(int(app_config.get("page_size", 200)))
        self._update_next_status()

    def _on_data_restored(self):
        """恢复备份后刷新所有页面数据。"""
        self.tasks_page.refresh()
        self.dashboard_page.refresh()
        self.history_page.refresh()
        self._update_next_status()

    def _sync_settings_page_size(self, n: int):
        """任务页分页菜单改每页条数后，让设置页下拉框同步显示。"""
        i = self.settings_page.cmb_page_size.findData(n)
        if i >= 0 and i != self.settings_page.cmb_page_size.currentIndex():
            self.settings_page.cmb_page_size.blockSignals(True)
            self.settings_page.cmb_page_size.setCurrentIndex(i)
            self.settings_page.cmb_page_size.blockSignals(False)

    def _apply_theme(self, theme_name: str, font_size: int):
        theme.apply_theme(QApplication.instance(), theme_name, font_size)

    def _update_next_status(self):
        _, total = repository.list_tasks(page=1, page_size=1)
        self.status_db.setText(f"共 {total} 条任务")
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
