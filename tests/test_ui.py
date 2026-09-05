"""UI 冒烟测试（QT_QPA_PLATFORM=offscreen）。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import Qt

from task_reminder import repository as repo
from task_reminder.models import TaskStatus, fmt


def mk(**kw):
    now = datetime.now()
    d = dict(name="界面冒烟任务", assignee="测试员", content="<b>内容</b>",
             deadline=fmt(now + timedelta(days=1)), reminder=fmt(now + timedelta(hours=1)))
    d.update(kw)
    tid = repo.add_task(d["name"], d["assignee"], d["content"], d["deadline"], d["reminder"])
    return tid


class TestModel:
    def test_model_rows_and_headers(self, qtbot):
        from task_reminder.ui.task_table_model import TaskTableModel
        from task_reminder.ui.widgets import COLUMNS
        tid = mk()
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        assert m.rowCount() == 1
        assert m.columnCount() == len(COLUMNS)
        assert m.headerData(0, Qt.Orientation.Horizontal) == "任务名称/摘要"
        assert m.task_at(0).id == tid

    def test_summary_fallback_to_content(self, qtbot):
        from task_reminder.ui.task_table_model import TaskTableModel
        repo.add_task("完整任务名称", "张三", "正文", "2026-09-10 10:00", "2026-09-09 09:00")
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        assert m.data(m.index(0, 0)) == "完整任务名称"


class TestTasksPage:
    def test_refresh_and_pagination(self, qtbot):
        for i in range(3):
            mk(name=f"页面任务名称{i}")
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.model.rowCount() == 3
        assert page.pager.total == 3
        page._on_page_size_changed(2)
        assert page.model.rowCount() <= 2

    def test_sort_visual_and_state(self, qtbot):
        mk()
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page._on_header_clicked(2)      # 截止时间列 → 升序
        assert page.sort_dir == "asc"
        idx = page.model.column_ids.index("deadline")
        header = page.view.horizontalHeader()
        assert header.sortIndicatorSection() == idx
        assert header.isSortIndicatorShown()
        page._on_header_clicked(2)      # → 降序
        assert page.sort_dir == "desc"
        page._on_header_clicked(2)      # → 默认
        assert page.sort_dir == ""
        assert header.sortIndicatorSection() == -1
        assert "默认" in page.current_sort_text()

    def test_column_hide_and_restore(self, qtbot):
        mk()
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        logical_notes = page.model.column_ids.index("notes")
        # 备注列默认隐藏
        assert page.view.horizontalHeader().isSectionHidden(logical_notes)
        page._toggle_column(logical_notes, True)
        assert not page.view.horizontalHeader().isSectionHidden(logical_notes)
        # 重置恢复默认（隐藏）
        page._reset_columns()
        assert page.view.horizontalHeader().isSectionHidden(logical_notes)

    def test_search_bar_criteria(self, qtbot):
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        bar.set_criteria({"keyword": "测试", "assignee": "张三",
                          "statuses": ["未开始"], "deadline_from": "2026-09-01 00:00"})
        c = bar.criteria()
        assert c["keyword"] == "测试"
        assert c["assignee"] == "张三"
        assert c["statuses"] == ["未开始"]
        assert c["deadline_from"] == "2026-09-01 00:00"


class TestTaskDialog:
    def test_validation_blocks_invalid(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("短")     # 名称过短
        assert dlg._validate() is not None
        assert not dlg.btn_ok.isEnabled()

    def test_valid_save_creates_task(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("对话框创建任务")
        dlg.edit_assignee.setText("张三")
        dlg.edit_content.setPlainText("正文内容")
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 10, 10, 0))
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 9, 9, 0))
        assert dlg._validate() is None
        dlg._on_save()
        assert dlg.task_id is not None
        t = repo.get_task(dlg.task_id)
        assert t.name == "对话框创建任务"
        assert t.content_plain() == "正文内容"

    def test_reminder_after_deadline_rejected(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("时间校验任务")
        dlg.edit_assignee.setText("张三")
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 9, 9, 0))
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 10, 10, 0))
        assert dlg._validate() == "提醒时间必须早于截止时间"


class TestMainWindow:
    def test_construct_and_switch(self, qtbot, monkeypatch):
        mk()
        from task_reminder.ui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win._switch_page(1)
        assert win.stack.currentIndex() == 1
        win._switch_page(2)
        assert win.stack.currentIndex() == 2
        win._switch_page(3)
        assert win.stack.currentIndex() == 3
        win._apply_theme("dark", 14)
        win._apply_theme("light", 13)
        win._switch_page(0)
        assert win.tasks_page.model.rowCount() == 1

    def test_close_hides_to_tray(self, qtbot):
        from task_reminder.ui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()
        win.close()
        assert not win.isVisible()       # 隐藏到托盘而非退出
