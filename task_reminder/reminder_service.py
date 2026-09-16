"""提醒调度服务：QTimer 轮询到期任务并发出信号。"""
from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import app_config, db, repository
from .models import Task

# 单个轮询周期最多触发的提醒数：防止长期未启动/积压大量过期任务时
# （声音、托盘气泡、弹窗、页面刷新）在主线程形成"风暴"导致界面卡死被杀。
# 未处理的任务留到下一个周期继续（最新的任务优先，见 due_for_reminder）。
MAX_PER_TICK = 20

logger = logging.getLogger("task_reminder")


class ReminderService(QObject):
    """按可配置间隔轮询数据库，到期任务批量触发 task_due_batch 信号。"""

    task_due_batch = pyqtSignal(list)   # [(Task, history_id), ...]，每批最多 MAX_PER_TICK 条

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
    def _query_due(self) -> list[Task]:
        """查询到期任务；数据库连接异常时自愈重连一次（避免异常被吞后永久静默）。"""
        try:
            return repository.due_for_reminder(limit=MAX_PER_TICK)
        except Exception as e:
            logger.warning("轮询查询失败，尝试重连数据库：%s", e)
            try:
                db.init(db.db_path())
            except Exception as e2:
                logger.error("数据库重连失败：%s", e2)
                return []
            try:
                return repository.due_for_reminder(limit=MAX_PER_TICK)
            except Exception as e2:
                logger.error("重连后查询仍失败：%s", e2)
                return []

    def tick(self) -> None:
        """单个轮询周期：跨日重置 + 分批触发到期提醒。"""
        self._maybe_reset_for_new_day()
        due = self._query_due()
        pairs: list[tuple[Task, int]] = []
        for task in due:
            try:
                history_id = repository.mark_triggered(task.id) or 0
            except Exception as e:
                # 单条标记失败不影响其余任务；该条保持 triggered=0 下轮重试
                logger.warning("标记任务 %s 已触发失败：%s", getattr(task, "id", "?"), e)
                continue
            pairs.append((task, history_id))
        if pairs:
            self.task_due_batch.emit(pairs)

    def _maybe_reset_for_new_day(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            try:
                repository.reset_triggered_for_new_day()
            except Exception as e:
                logger.warning("跨日重置失败：%s", e)
            self._last_reset_date = today
