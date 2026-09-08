"""提醒历史页：时间范围筛选 + 分页 + 单条删除 + 清空。"""
from __future__ import annotations

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (QComboBox, QDateEdit, QHBoxLayout, QHeaderView,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from .. import repository
from .search_bar import add_calendar_year_buttons
from .widgets import confirm

QUICK = {"全部": None, "今天": 0, "近7天": 7, "近30天": 30}


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_no = 1
        self.page_size = 50
        self._auto_range = True    # 自动跟随当前时间；用户手动改时间后锁定
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        self.cmb_quick = QComboBox()
        self.cmb_quick.addItems(list(QUICK.keys()))
        self.dt_from = QDateEdit()
        self.dt_to = QDateEdit()
        for w in (self.dt_from, self.dt_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.setDate(QDate.currentDate())
            w.setFixedWidth(130)
            add_calendar_year_buttons(w)
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

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["触发时间", "任务内容", "执行人", "截止时间", "响应操作", "响应时间", "操作"])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 140)
        self.table.setColumnWidth(6, 60)
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
        # 手动改时间：锁定自动范围并立即生效
        self.dt_from.dateChanged.connect(self._on_manual_range)
        self.dt_to.dateChanged.connect(self._on_manual_range)
        self.btn_prev.clicked.connect(lambda: self._turn(-1))
        self.btn_next.clicked.connect(lambda: self._turn(1))

    def _on_manual_range(self):
        """用户手动修改时间范围后：不再自动覆盖，并立即刷新。"""
        self._auto_range = False
        self.page_no = 1
        self.refresh()

    def _apply_auto_range(self):
        """按快捷范围自动计算起止时间。

        - "全部"：不限制起始，UI 上 dt_from 保持当前值（避免日历停在 2000 年），
          查询时 from 传空字符串。
        - "今天"/"近N天"：按日期范围计算。
        """
        key = self.cmb_quick.currentText()
        days = QUICK[key]
        today = QDate.currentDate()
        if days is None:
            start = None  # 全部：不设起始限制
        elif days == 0:
            start = today
        else:
            start = today.addDays(-days)
        self.dt_to.blockSignals(True)
        self.dt_to.setDate(today)
        self.dt_to.blockSignals(False)
        if start is not None:
            self.dt_from.blockSignals(True)
            self.dt_from.setDate(start)
            self.dt_from.blockSignals(False)

    def _on_quick(self):
        self._auto_range = True
        self.page_no = 1
        self.refresh()

    def _on_query(self):
        self.page_no = 1
        self.refresh()

    def _turn(self, d: int):
        pages = getattr(self, "_pages", 1)
        self.page_no = max(1, min(self.page_no + d, pages))
        self.refresh()

    def refresh(self):
        if self._auto_range:
            self._apply_auto_range()
        # "全部"范围时 start 留空（不限制起始），避免 UI 上 dt_from 停在 2000 年
        if self._auto_range and self.cmb_quick.currentText() == "全部":
            start = ""
        else:
            start = self.dt_from.date().toString("yyyy-MM-dd") + " 00:00"
        end = self.dt_to.date().toString("yyyy-MM-dd") + " 23:59"
        logs, total = repository.list_history(self.page_no, self.page_size, start, end)
        self.table.setRowCount(0)
        for lg in logs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [lg.triggered_at, (lg.content_snapshot or "")[:60], lg.assignee,
                     lg.deadline, lg.response_text(), lg.responded_at]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if lg.response == "done":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    elif lg.response in ("", None):
                        item.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(row, col, item)
            # 删除按钮
            btn_del = QPushButton("删除")
            btn_del.setObjectName("btnDanger")
            btn_del.setFixedWidth(50)
            btn_del.clicked.connect(lambda _, hid=lg.id: self._delete_row(hid))
            self.table.setCellWidget(row, 6, btn_del)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        self._pages = pages
        self.lbl_info.setText(f"共 {total} 条　第 {self.page_no}/{pages} 页")
        self.btn_prev.setEnabled(self.page_no > 1)
        self.btn_next.setEnabled(self.page_no < pages)

    def _delete_row(self, history_id: int):
        if not confirm(self, "删除历史记录", "确定删除这一条提醒历史吗？"):
            return
        repository.delete_history_row(history_id)
        self.refresh()

    def _on_clear(self):
        if not confirm(self, "清空提醒历史",
                       "确定清空全部提醒历史吗？\n此操作不可恢复，建议先在设置页备份。"):
            return
        repository.clear_history()
        self.refresh()
