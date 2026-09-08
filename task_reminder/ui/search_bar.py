"""高级搜索面板：任务名称 / 内容关键词分开搜索 + 日期范围可开关 + 实时防抖。"""
from __future__ import annotations

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)


def make_year_buttons(date_edit: QDateEdit) -> tuple[QPushButton, QPushButton]:
    """为日期框生成一对翻年按钮（« 上一年 / 下一年 »），与日历内单箭头翻月区分。"""
    prev = QPushButton("«")
    nxt = QPushButton("»")
    for btn in (prev, nxt):
        btn.setObjectName("btnYear")
        btn.setFixedWidth(28)
    prev.setToolTip("上一年")
    nxt.setToolTip("下一年")
    prev.clicked.connect(lambda: date_edit.setDate(date_edit.date().addYears(-1)))
    nxt.clicked.connect(lambda: date_edit.setDate(date_edit.date().addYears(1)))
    return prev, nxt


class SearchBar(QWidget):
    """快速框按任务名称搜索；高级面板提供内容关键词、执行人、状态、日期范围。"""

    changed = pyqtSignal(dict)     # 防抖后的完整条件

    # 高级面板中可被设置/清空的字段（用于"收起后条件仍生效"提示与重置）
    _ADV_KEYS = ("content_kw", "assignee", "statuses", "created", "deadline")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._emit)
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        # 快捷行：名称搜索 + 高级切换 + 收起时的生效提示 + 重置
        quick = QHBoxLayout()
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText("按任务名称搜索（实时，空格分隔多个词）")
        self.edit_keyword.setClearButtonEnabled(True)
        self.edit_keyword.textChanged.connect(self._debounce.start)
        self.btn_advanced = QPushButton("高级搜索")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setObjectName("btnGhost")
        self.btn_advanced.toggled.connect(self._toggle_advanced)
        self.btn_active = QPushButton("")       # 收起时显示"已启用 N 项筛选"
        self.btn_active.setObjectName("btnGhost")
        self.btn_active.setVisible(False)
        self.btn_active.clicked.connect(lambda: self.btn_advanced.setChecked(True))
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setObjectName("btnRow")
        self.btn_reset.clicked.connect(self.reset)
        quick.addWidget(self.edit_keyword, 1)
        quick.addWidget(self.btn_active)
        quick.addWidget(self.btn_advanced)
        quick.addWidget(self.btn_reset)
        outer.addLayout(quick)

        # 高级面板
        self.panel = QWidget()
        grid = QGridLayout(self.panel)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        # 内容关键词（含备注）
        grid.addWidget(QLabel("内容关键词："), 0, 0)
        self.edit_content_kw = QLineEdit()
        self.edit_content_kw.setPlaceholderText("在任务内容和备注中搜索，空格分隔多个词")
        self.edit_content_kw.setClearButtonEnabled(True)
        self.edit_content_kw.textChanged.connect(self._debounce.start)
        grid.addWidget(self.edit_content_kw, 0, 1, 1, 3)

        # 执行人
        grid.addWidget(QLabel("执行人："), 1, 0)
        self.edit_assignee = QLineEdit()
        self.edit_assignee.setPlaceholderText("精确匹配")
        self.edit_assignee.textChanged.connect(self._debounce.start)
        grid.addWidget(self.edit_assignee, 1, 1)
        grid.addWidget(QLabel("状态："), 1, 2)
        status_row = QHBoxLayout()
        self.chk_status = {}
        for s in ("未开始", "进行中", "已完成"):
            cb = QCheckBox(s)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_status_changed)
            self.chk_status[s] = cb
            status_row.addWidget(cb)
        status_row.addStretch(1)
        grid.addLayout(status_row, 1, 3)

        # 日期范围：带启用开关，取消勾选即恢复"不限"。
        # 每个日期框两侧加翻年按钮（« » 双箭头），区别于日历弹出框内的单箭头 ◀ ▶（翻月）。
        self._date_ranges = {}
        for r, (label, key) in enumerate([("创建时间：", "created"), ("截止时间：", "deadline")],
                                         start=2):
            grid.addWidget(QLabel(label), r, 0)
            chk = QCheckBox("限定")
            grid.addWidget(chk, r, 1)
            lo, hi = QDateEdit(), QDateEdit()
            for w in (lo, hi):
                w.setCalendarPopup(True)
                w.setDisplayFormat("yyyy-MM-dd")
                w.setMinimumDate(QDate(2000, 1, 1))
                w.setMaximumDate(QDate(2200, 12, 31))
                w.setDate(QDate.currentDate())
                w.setFixedWidth(130)
                w.dateChanged.connect(self._debounce.start)
            chk.toggled.connect(self._on_range_toggled)
            # 起始：«  从  [lo]  »
            lo_prev, lo_next = make_year_buttons(lo)
            grid.addWidget(QLabel("从"), r, 2, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(lo_prev, r, 3)
            grid.addWidget(lo, r, 4)
            grid.addWidget(lo_next, r, 5)
            # 结束：至  «  [hi]  »
            hi_prev, hi_next = make_year_buttons(hi)
            grid.addWidget(QLabel("至"), r, 6, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(hi_prev, r, 7)
            grid.addWidget(hi, r, 8)
            grid.addWidget(hi_next, r, 9)
            self._date_ranges[key] = {"chk": chk, "lo": lo, "hi": hi}

        self.panel.hide()
        outer.addWidget(self.panel)

    # ------------------------------------------------------------------
    def _toggle_advanced(self, checked: bool) -> None:
        self.panel.setVisible(checked)
        self.btn_advanced.setText("收起条件" if checked else "高级搜索")
        self._update_active_badge()

    def _on_status_changed(self, _state: int) -> None:
        # 全部取消 = 全部显示，语义反直觉：自动勾回全部
        if not any(cb.isChecked() for cb in self.chk_status.values()):
            for cb in self.chk_status.values():
                cb.blockSignals(True)
                cb.setChecked(True)
                cb.blockSignals(False)
        self._debounce.start()

    def _on_range_toggled(self, checked: bool) -> None:
        """复选框仅控制是否生效，日期始终可编辑、不重置到 2000 年。"""
        self._debounce.start()

    def _emit(self) -> None:
        self._update_active_badge()
        self.changed.emit(self.criteria())

    def _update_active_badge(self) -> None:
        """面板收起时显示当前生效的高级条件数，避免'静默过滤'。"""
        n = len(self.adv_keys_in_use())
        self.btn_active.setVisible(bool(n) and not self.btn_advanced.isChecked())
        self.btn_active.setText(f"已启用 {n} 项筛选")

    def adv_keys_in_use(self) -> list[str]:
        c = self.criteria()
        used = []
        if c.get("content_kw"):
            used.append("content_kw")
        if c.get("assignee"):
            used.append("assignee")
        if c.get("statuses"):
            used.append("statuses")
        if c.get("created_from") or c.get("created_to"):
            used.append("created")
        if c.get("deadline_from") or c.get("deadline_to"):
            used.append("deadline")
        return used

    # ------------------------------------------------------------------
    def criteria(self) -> dict:
        c: dict = {}
        if self.edit_keyword.text().strip():
            c["keyword"] = self.edit_keyword.text().strip()
        if self.edit_content_kw.text().strip():
            c["content_kw"] = self.edit_content_kw.text().strip()
        if self.edit_assignee.text().strip():
            c["assignee"] = self.edit_assignee.text().strip()
        statuses = [s for s, cb in self.chk_status.items() if cb.isChecked()]
        if len(statuses) < 3:
            c["statuses"] = statuses
        for key in ("created", "deadline"):
            rng = self._date_ranges[key]
            if not rng["chk"].isChecked():
                continue
            c[f"{key}_from"] = rng["lo"].date().toString("yyyy-MM-dd") + " 00:00"
            c[f"{key}_to"] = rng["hi"].date().toString("yyyy-MM-dd") + " 23:59"
        return c

    def set_criteria(self, c: dict) -> None:
        self.edit_keyword.setText(c.get("keyword", ""))
        self.edit_content_kw.setText(c.get("content_kw", ""))
        self.edit_assignee.setText(c.get("assignee", ""))
        statuses = c.get("statuses")
        for s, cb in self.chk_status.items():
            cb.setChecked(True if statuses is None else s in statuses)
        for key in ("created", "deadline"):
            rng = self._date_ranges[key]
            has = bool(c.get(f"{key}_from") or c.get(f"{key}_to"))
            rng["chk"].blockSignals(True)
            rng["chk"].setChecked(has)
            rng["chk"].blockSignals(False)
            if has:
                self._set_range_date(rng["lo"], c.get(f"{key}_from"))
                self._set_range_date(rng["hi"], c.get(f"{key}_to"))
            else:
                today = QDate.currentDate()
                for w in (rng["lo"], rng["hi"]):
                    w.blockSignals(True)
                    w.setDate(today)
                    w.blockSignals(False)
        self._update_active_badge()
        self._debounce.start()

    @staticmethod
    def _set_range_date(edit: QDateEdit, value) -> None:
        if not value:
            return
        d = QDate.fromString(str(value)[:10], "yyyy-MM-dd")
        if d.isValid():
            edit.setDate(d)

    def reset(self) -> None:
        self.set_criteria({})
