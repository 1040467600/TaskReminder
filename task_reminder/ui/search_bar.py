"""高级搜索面板：实时防抖搜索 + 保存/加载常用搜索条件。"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from .. import repository


class SearchBar(QWidget):
    """关键词实时搜索 + 可折叠高级条件 + 保存的搜索条件管理。"""

    changed = pyqtSignal(dict)     # 防抖后的完整条件

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._emit)
        self._build()
        self.reload_saved_searches()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        # 快捷行
        quick = QHBoxLayout()
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText("搜索任务名称 / 内容关键词（实时）")
        self.edit_keyword.setClearButtonEnabled(True)
        self.btn_advanced = QPushButton("高级搜索")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setObjectName("btnGhost")
        self.edit_keyword.textChanged.connect(self._debounce.start)
        self.btn_advanced.toggled.connect(self._toggle_advanced)
        quick.addWidget(self.edit_keyword, 1)
        quick.addWidget(self.btn_advanced)
        outer.addLayout(quick)

        # 高级面板
        self.panel = QWidget()
        grid = QGridLayout(self.panel)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("执行人："), 0, 0)
        self.edit_assignee = QLineEdit()
        self.edit_assignee.setPlaceholderText("精确匹配")
        self.edit_assignee.textChanged.connect(self._debounce.start)
        grid.addWidget(self.edit_assignee, 0, 1)

        grid.addWidget(QLabel("状态："), 0, 2)
        status_row = QHBoxLayout()
        self.chk_status = {}
        for s in ("未开始", "进行中", "已完成"):
            cb = QCheckBox(s)
            cb.setChecked(True)
            cb.stateChanged.connect(self._debounce.start)
            self.chk_status[s] = cb
            status_row.addWidget(cb)
        status_row.addStretch(1)
        grid.addLayout(status_row, 0, 3)

        labels_ranges = [
            ("创建时间：", "created"),
            ("截止时间：", "deadline"),
        ]
        for r, (label, key) in enumerate(labels_ranges, start=1):
            grid.addWidget(QLabel(label), r, 0)
            lo, hi = QDateEdit(), QDateEdit()
            for w in (lo, hi):
                w.setCalendarPopup(True)
                w.setDisplayFormat("yyyy-MM-dd")
                w.setSpecialValueText("不限")
                w.setMinimumDate(QDate(2000, 1, 1))
                w.setDate(QDate(2000, 1, 1))
                w.dateChanged.connect(self._debounce.start)
            grid.addWidget(lo, r, 1)
            grid.addWidget(QLabel("至"), r, 1 + 1)
            grid.addWidget(hi, r, 3)
            setattr(self, f"d_{key}_lo", lo)
            setattr(self, f"d_{key}_hi", hi)

        # 保存的搜索条件
        grid.addWidget(QLabel("常用搜索："), 3, 0)
        self.cmb_saved = QComboBox()
        self.cmb_saved.setMinimumWidth(160)
        self.btn_load = QPushButton("加载")
        self.btn_save = QPushButton("保存当前")
        self.btn_del = QPushButton("删除")
        for b in (self.btn_load, self.btn_save, self.btn_del):
            b.setObjectName("btnRow")
        self.btn_load.clicked.connect(self._load_saved)
        self.btn_save.clicked.connect(self._save_current)
        self.btn_del.clicked.connect(self._delete_saved)
        grid.addWidget(self.cmb_saved, 3, 1, 1, 2)
        row_btns = QHBoxLayout()
        row_btns.addWidget(self.btn_load)
        row_btns.addWidget(self.btn_save)
        row_btns.addWidget(self.btn_del)
        row_btns.addStretch(1)
        grid.addLayout(row_btns, 3, 3)

        self.panel.hide()
        outer.addWidget(self.panel)

    # ------------------------------------------------------------------
    def _toggle_advanced(self, checked: bool) -> None:
        self.panel.setVisible(checked)
        self.btn_advanced.setText("收起条件" if checked else "高级搜索")

    def _emit(self) -> None:
        self.changed.emit(self.criteria())

    def criteria(self) -> dict:
        c: dict = {}
        if self.edit_keyword.text().strip():
            c["keyword"] = self.edit_keyword.text().strip()
        if self.edit_assignee.text().strip():
            c["assignee"] = self.edit_assignee.text().strip()
        statuses = [s for s, cb in self.chk_status.items() if cb.isChecked()]
        if len(statuses) < 3:
            c["statuses"] = statuses
        for key in ("created", "deadline"):
            lo: QDateEdit = getattr(self, f"d_{key}_lo")
            hi: QDateEdit = getattr(self, f"d_{key}_hi")
            if lo.date() != lo.minimumDate():
                c[f"{key}_from"] = lo.date().toString("yyyy-MM-dd") + " 00:00"
            if hi.date() != hi.minimumDate():
                c[f"{key}_to"] = hi.date().toString("yyyy-MM-dd") + " 23:59"
        return c

    def set_criteria(self, c: dict) -> None:
        self.edit_keyword.setText(c.get("keyword", ""))
        self.edit_assignee.setText(c.get("assignee", ""))
        statuses = c.get("statuses")
        for s, cb in self.chk_status.items():
            cb.setChecked(True if statuses is None else s in statuses)
        for key in ("created", "deadline"):
            lo: QDateEdit = getattr(self, f"d_{key}_lo")
            hi: QDateEdit = getattr(self, f"d_{key}_hi")
            self._set_range_date(lo, c.get(f"{key}_from"))
            self._set_range_date(hi, c.get(f"{key}_to"), hi=True)
        self._debounce.start()

    @staticmethod
    def _set_range_date(edit: QDateEdit, value, hi=False) -> None:
        if not value:
            edit.setDate(edit.minimumDate())
            return
        d = QDate.fromString(str(value)[:10], "yyyy-MM-dd")
        edit.setDate(d if d.isValid() else edit.minimumDate())

    def reset(self) -> None:
        self.set_criteria({})

    # ------------------------------------------------------------------
    def reload_saved_searches(self) -> None:
        self.cmb_saved.clear()
        for item in repository.list_searches():
            self.cmb_saved.addItem(item["name"], item)

    def _load_saved(self) -> None:
        item = self.cmb_saved.currentData()
        if item:
            self.set_criteria(item["criteria"])

    def _save_current(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "保存搜索条件", "条件名称：")
        if ok and name.strip():
            repository.save_search(name.strip(), self.criteria())
            self.reload_saved_searches()
            idx = self.cmb_saved.findText(name.strip())
            self.cmb_saved.setCurrentIndex(max(0, idx))

    def _delete_saved(self) -> None:
        item = self.cmb_saved.currentData()
        if item:
            repository.delete_search(item["id"])
            self.reload_saved_searches()

    # 快捷：今天创建
    def quick_today(self) -> None:
        today = QDate.currentDate()
        self.panel.show()
        self.btn_advanced.setChecked(True)
        self.d_created_lo.setDate(today)
        self.d_created_hi.setDate(today)
