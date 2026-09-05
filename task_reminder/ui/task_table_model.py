"""任务表格模型：按当前列配置输出任务数据。"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from ..models import Task, TaskStatus
from .widgets import COLUMNS, deadline_foreground


class TaskTableModel(QAbstractTableModel):
    """列顺序/可见性由 column_ids 决定（与 COLUMNS 定义对应）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[Task] = []
        self.column_ids: list[str] = [c[0] for c in COLUMNS]
        self.column_titles: dict[str, str] = {c[0]: c[1] for c in COLUMNS}

    # ------------------------------------------------------------------
    def set_columns(self, ids: list[str]) -> None:
        self.beginResetModel()
        self.column_ids = ids
        self.endResetModel()

    def set_tasks(self, tasks: list[Task]) -> None:
        self.beginResetModel()
        self._tasks = tasks
        self.endResetModel()

    def task_at(self, row: int) -> Task | None:
        return self._tasks[row] if 0 <= row < len(self._tasks) else None

    def all_tasks(self) -> list[Task]:
        return list(self._tasks)

    # ------------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.column_ids)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            cid = self.column_ids[section]
            return self.column_titles.get(cid, cid)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        cid = self.column_ids[index.column()]
        if role == Qt.ItemDataRole.UserRole:
            if cid == "status":
                return task.status
            if cid == "actions":
                return task.id
            return None
        if cid == "actions":
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if cid == "name":
                return task.summary()
            if cid == "assignee":
                return task.assignee
            if cid == "deadline":
                return task.deadline
            if cid == "reminder_time":
                return task.reminder_time
            if cid == "status":
                return task.status
            if cid == "notes":
                return task.notes or ""
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = f"【{task.summary()}】\n执行人：{task.assignee}\n截止：{task.deadline}\n提醒：{task.reminder_time}"
            plain = task.content_plain()
            if plain:
                tip += f"\n内容：{plain[:200]}"
            return tip
        if role == Qt.ItemDataRole.ForegroundRole and cid in ("deadline", "reminder_time"):
            fg = deadline_foreground(task)
            return fg
        if role == Qt.ItemDataRole.TextAlignmentRole and cid in ("status",):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None
