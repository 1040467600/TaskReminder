"""数据看板页：统计卡片 + 状态分布图 + 即将到期/已过期列表。"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QVBoxLayout, QWidget)

from .. import repository
from ..models import TaskStatus
from .widgets import STATUS_COLORS


class StatCard(QFrame):
    clicked = pyqtSignal(str)      # 卡片 key

    def __init__(self, title: str, color_key: str, key: str = "", parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("card")
        self.setToolTip("点击查看对应任务")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("cardTitle")
        self.lbl_value = QLabel("0")
        self.lbl_value.setObjectName("cardValue")
        self.lbl_value.setProperty("themeColor", color_key)
        v.addWidget(self.lbl_title)
        v.addWidget(self.lbl_value)

    def set_value(self, n: int):
        self.lbl_value.setText(str(n))

    def mousePressEvent(self, ev):
        self.clicked.emit(self.key)
        super().mousePressEvent(ev)


class BarChart(QWidget):
    """简易状态分布柱状图（QPainter，无第三方依赖）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self._data: list[tuple[str, int, str]] = []   # (label, value, color)

    def set_data(self, data: list[tuple[str, int, str]]):
        self._data = data
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        max_v = max((v for _, v, _ in self._data), default=1) or 1
        bar_w = min(72, w // max(1, len(self._data)) - 24)
        baseline = h - 26
        x = (w - (bar_w + 40) * len(self._data)) // 2 + 20
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        for label, value, color in self._data:
            bh = int((h - 60) * value / max_v)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRect(x - bar_w // 2, baseline - bh, bar_w, max(bh, 4)), 6, 6)
            painter.setPen(QColor("#64748B"))
            painter.drawText(QRect(x - 40, baseline - bh - 20, 80, 16),
                             Qt.AlignmentFlag.AlignCenter, str(value))
            painter.drawText(QRect(x - 40, baseline + 4, 80, 18),
                             Qt.AlignmentFlag.AlignCenter, label)
            x += bar_w + 40


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(10)

        title = QLabel("数据看板")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # 统计卡片（点击可跳转到任务页并应用对应筛选）
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_total = StatCard("任务总数", "blue", key="total")
        self.card_notstarted = StatCard("未开始", "gray", key="notstarted")
        self.card_inprogress = StatCard("进行中", "amber", key="inprogress")
        self.card_done = StatCard("已完成", "green", key="done")
        self.card_overdue = StatCard("已过期", "red", key="overdue")
        self.card_week = StatCard("7 天内到期", "blue", key="week")
        for c in (self.card_total, self.card_notstarted, self.card_inprogress,
                  self.card_done, self.card_overdue, self.card_week):
            cards.addWidget(c, 1)
        layout.addLayout(cards)

        body = QHBoxLayout()
        body.setSpacing(10)

        # 柱状图
        self.chart_card = QFrame()
        self.chart_card.setObjectName("card")
        cv = QVBoxLayout(self.chart_card)
        cv.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel("任务状态分布")
        lbl.setObjectName("cardTitle")
        self.chart = BarChart()
        cv.addWidget(lbl)
        cv.addWidget(self.chart, 1)
        body.addWidget(self.chart_card, 1)

        # 列表
        lists = QVBoxLayout()
        lists.setSpacing(10)
        self.list_upcoming = self._list("即将提醒（最近 10 条）")
        self.list_overdue = self._list("已过期未完成（最近 10 条）")
        lists.addWidget(self.list_upcoming["widget"], 1)
        lists.addWidget(self.list_overdue["widget"], 1)
        body.addLayout(lists, 1)
        layout.addLayout(body, 1)

    def _list(self, title: str) -> dict:
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(title)
        lbl.setObjectName("cardTitle")
        lw = QListWidget()
        lw.setObjectName("dashList")
        v.addWidget(lbl)
        v.addWidget(lw)
        return {"widget": frame, "list": lw}

    def refresh(self):
        s = repository.stats()
        self.card_total.set_value(s["total"])
        self.card_notstarted.set_value(s["by_status"][TaskStatus.NOT_STARTED])
        self.card_inprogress.set_value(s["by_status"][TaskStatus.IN_PROGRESS])
        self.card_done.set_value(s["by_status"][TaskStatus.DONE])
        self.card_overdue.set_value(s["overdue"])
        self.card_week.set_value(s["due_week"])
        self.chart.set_data([
            (TaskStatus.NOT_STARTED, s["by_status"][TaskStatus.NOT_STARTED], STATUS_COLORS[TaskStatus.NOT_STARTED][0]),
            (TaskStatus.IN_PROGRESS, s["by_status"][TaskStatus.IN_PROGRESS], STATUS_COLORS[TaskStatus.IN_PROGRESS][0]),
            (TaskStatus.DONE, s["by_status"][TaskStatus.DONE], STATUS_COLORS[TaskStatus.DONE][0]),
        ])
        up = self.list_upcoming["list"]
        up.clear()
        upcoming = repository.upcoming_reminders(10)
        for t in upcoming:
            up.addItem(QListWidgetItem(f"⏰ {t.reminder_time}　{t.summary()}　（{t.assignee}）"))
        if not upcoming:
            up.addItem(QListWidgetItem("暂无即将到来的提醒"))
        od = self.list_overdue["list"]
        od.clear()
        overdue = repository.overdue_tasks(10)
        for t in overdue:
            od.addItem(QListWidgetItem(f"⚠️ {t.deadline}　{t.summary()}　（{t.assignee}）"))
        if not overdue:
            od.addItem(QListWidgetItem("没有过期任务，保持得很好"))
