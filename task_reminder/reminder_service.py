"""提醒调度服务：QTimer 轮询到期任务并发出信号。"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import app_config, repository
from .models import Task


class ReminderService(QObject):
    """按可配置间隔轮询数据库，到期任务触发 task_due 信号。"""

    task_due = pyqtSignal(object, int)   # (Task, history_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        self._last_reset_date = ""

    # ------------------------------------------------------------------
    def start(self) -> None:
        self.apply_interval()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def apply_interval(self) -> None:
        """从配置读取轮询间隔（1-60 秒）。"""
        try:
            sec = int(app_config.get("poll_interval", 5))
        except (TypeError, ValueError):
            sec = 5
        sec = max(1, min(60, sec))
        self._timer.setInterval(sec * 1000)

    def next_check_text(self) -> str:
        ms = self._timer.remainingTime()
        if ms < 0:
            return "-"
        return datetime.now().strftime("%H:%M:%S")

    # ------------------------------------------------------------------
    def tick(self) -> None:
        """单个轮询周期：跨日重置 + 触发到期提醒。"""
        self._maybe_reset_for_new_day()
        try:
            due = repository.due_for_reminder()
        except Exception:
            return
        for task in due:
            history_id = repository.mark_triggered(task.id) or 0
            self.task_due.emit(task, history_id)

    def _maybe_reset_for_new_day(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            repository.reset_triggered_for_new_day()
            self._last_reset_date = today
