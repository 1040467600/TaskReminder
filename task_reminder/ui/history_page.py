"""提醒历史页：时间范围筛选 + 分页 + 清空。"""
from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (QComboBox, QDateTimeEdit, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from .. import repository
from ..models import parse

QUICK = {"全部": None, "今天": 0, "近7天": 7, "近30天": 30}


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_no = 1
        self.page_size = 50
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        self.cmb_quick = QComboBox()
        self.cmb_quick.addItems(list(QUICK.keys()))
        self.dt_from = QDateTimeEdit()
        self.dt_to = QDateTimeEdit()
        for w in (self.dt_from, self.dt_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_from.setDateTime(QDateTime(datetime.now().replace(hour=0, minute=0)))
        self.dt_to.setDateTime(QDateTime(datetime.now()))
        self.btn_query = QPushButton("查询")
        self.btn_query.setObjectName("btnPrimary")
        self.btn_clear = QPushButton("清空历史")
        self.btn_clear.setObjectName("btnDanger")
        bar.addWidget(QLabel("快捷范围："))
        bar.addWidget(self.cmb_quick)
        bar.addWidget(QLabel("从"))
        bar.addWidget(self.dt_from)
        bar.addWidget(QLabel("至"))
        bar.addWidget(self.dt_to)
        bar.addWidget(self.btn_query)
        bar.addStretch(1)
        bar.addWidget(self.btn_clear)
        layout.addLayout(bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["触发时间", "任务内容", "执行人", "截止时间", "响应操作", "响应时间"])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.lbl_info = QLabel("共 0 条")
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        for b in (self.btn_prev, self.btn_next):
            b.setObjectName("btnRow")
        foot.addWidget(self.lbl_info)
        foot.addStretch(1)
        foot.addWidget(self.btn_prev)
        foot.addWidget(self.btn_next)
        layout.addLayout(foot)

        self.btn_query.clicked.connect(self._on_query)
        self.btn_clear.clicked.connect(self._on_clear)
        self.cmb_quick.currentIndexChanged.connect(self._on_quick)
        self.btn_prev.clicked.connect(lambda: self._turn(-1))
        self.btn_next.clicked.connect(lambda: self._turn(1))

    def _on_quick(self):
        key = self.cmb_quick.currentText()
        days = QUICK.get(key)
        if days is None:
            return
        now = datetime.now()
        if days == 0:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now - timedelta(days=days)
        self.dt_from.setDateTime(QDateTime(start))
        self.dt_to.setDateTime(QDateTime(now))
        self._on_query()

    def _on_query(self):
        self.page_no = 1
        self.refresh()

    def _turn(self, d: int):
        self.page_no = max(1, self.page_no + d)
        self.refresh()

    def refresh(self):
        start = self.dt_from.dateTime().toString("yyyy-MM-dd HH:mm")
        end = self.dt_to.dateTime().toString("yyyy-MM-dd HH:mm")
        logs, total = repository.list_history(self.page_no, self.page_size, start, end)
        self.table.setRowCount(0)
        for lg in logs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [lg.triggered_at, (lg.content_snapshot or "")[:60], lg.assignee,
                     lg.deadline, lg.response_text(), lg.responded_at]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if lg.response == "done":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    elif lg.response in ("", None):
                        item.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(row, col, item)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.lbl_info.setText(f"共 {total} 条　第 {self.page_no}/{pages} 页")
        self.btn_prev.setEnabled(self.page_no > 1)
        self.btn_next.setEnabled(self.page_no < pages)

    def _on_clear(self):
        if QMessageBox.question(self, "清空提醒历史", "确定清空全部提醒历史吗？此操作不可恢复。",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            repository.clear_history()
            self.refresh()
