"""UI 冒烟测试（QT_QPA_PLATFORM=offscreen）。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

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

    def test_new_task_button_visible_left_of_edit(self, qtbot):
        """新建任务按钮必须显示，且位于编辑按钮左边。"""
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page.show()
        QApplication.processEvents()
        assert page.btn_new.isVisibleTo(page)
        assert "新建任务" in page.btn_new.text()
        assert page.btn_new.geometry().x() < page.btn_edit.geometry().x()

    def test_empty_hint_toggles(self, qtbot):
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        page.refresh()
        assert page.empty_hint.isVisibleTo(page.view.viewport())
        mk()
        page.refresh()
        assert not page.empty_hint.isVisibleTo(page.view.viewport())


    def test_saved_column_state_restores_delegates(self, qtbot):
        """回归：保存过列配置后重新打开页面，状态徽章/操作列委托必须仍绑定
        （app_config.get 已解析 JSON，重复 json.loads 会抛 TypeError 被吞）。"""
        import json as _json
        from task_reminder import app_config
        from task_reminder.ui.tasks_page import TasksPage
        from task_reminder.ui.widgets import StatusDelegate, ActionDelegate
        mk()
        # 模拟老用户已保存的列配置 + 排序状态
        app_config.set("column_state", _json.dumps([
            {"id": "name", "visible": True, "width": 260},
            {"id": "assignee", "visible": True, "width": 100},
            {"id": "deadline", "visible": True, "width": 150},
            {"id": "reminder_time", "visible": True, "width": 150},
            {"id": "status", "visible": True, "width": 96},
            {"id": "notes", "visible": False, "width": 180},
            {"id": "actions", "visible": True, "width": 132},
        ], ensure_ascii=False))
        app_config.set("sort_state", _json.dumps({"key": "deadline", "dir": "asc"}))
        page = TasksPage()
        qtbot.addWidget(page)
        ids = page.model.column_ids
        d_status = page.view.itemDelegateForColumn(ids.index("status"))
        d_actions = page.view.itemDelegateForColumn(ids.index("actions"))
        assert isinstance(d_status, StatusDelegate)
        assert isinstance(d_actions, ActionDelegate)
        assert page.sort_key == "deadline" and page.sort_dir == "asc"


class TestThemeIndicators:
    def test_radio_and_checkbox_indicators_styled(self):
        """QSS 命中 QRadioButton/QCheckBox 时必须显式定义 ::indicator，
        否则原生圆圈/方框不再绘制（导出范围对话框单选钮消失的回归点）。"""
        from task_reminder.ui.theme import theme_qss
        for theme in ("light", "dark"):
            qss = theme_qss(theme)
            assert "{CHECK_PNG}" not in qss
            assert "QRadioButton::indicator:checked" in qss
            assert "QCheckBox::indicator:checked" in qss
            assert "check.png" in qss


class TestTaskDialog:
    def test_validation_blocks_invalid(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("")       # 名称不能为空（下限 1 字符）
        assert dlg._validate() is not None
        assert not dlg.btn_ok.isEnabled()

    def test_fmt_buttons_no_crash_and_toggle(self, qtbot):
        """回归：点击 B/I/U 不得使进程崩溃（旧代码 merge() 返回 None 传入
        setCurrentCharFormat → 槽内 TypeError → qFatal 闪退）。"""
        from PyQt6.QtGui import QFont
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_content.setPlainText("富文本内容")
        dlg.show()                      # 必须可见，模拟真实点击
        # 无选中时点击 B：加粗当前输入格式
        qtbot.mouseClick(dlg.btn_bold, Qt.MouseButton.LeftButton)
        f = dlg.edit_content.currentCharFormat()
        assert f.fontWeight() == QFont.Weight.Bold
        assert dlg.btn_bold.isChecked()
        # 再点一次取消加粗
        qtbot.mouseClick(dlg.btn_bold, Qt.MouseButton.LeftButton)
        assert dlg.edit_content.currentCharFormat().fontWeight() != QFont.Weight.Bold
        # I / U 同样操作
        qtbot.mouseClick(dlg.btn_italic, Qt.MouseButton.LeftButton)
        assert dlg.edit_content.currentCharFormat().fontItalic()
        qtbot.mouseClick(dlg.btn_underline, Qt.MouseButton.LeftButton)
        assert dlg.edit_content.currentCharFormat().fontUnderline()
        # 清除格式
        qtbot.mouseClick(dlg.btn_clear_fmt, Qt.MouseButton.LeftButton)
        f = dlg.edit_content.currentCharFormat()
        assert not f.fontItalic() and not f.fontUnderline()

    def test_fmt_on_selection(self, qtbot):
        """选中文字后点击 B：选区字符加粗。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_content.setPlainText("选我加粗")
        cursor = dlg.edit_content.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(2, cursor.MoveMode.KeepAnchor)
        dlg.edit_content.setTextCursor(cursor)
        dlg._fmt(bold=True)
        html = dlg.edit_content.toHtml()
        assert "bold" in html.lower() or "font-weight" in html.lower()

    def test_one_char_names_valid(self, qtbot):
        """名称/执行人 1 字符即可通过校验。"""
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("A")
        dlg.edit_assignee.setText("李")
        dlg.edit_content.setPlainText("x")
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 10, 10, 0))
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 9, 9, 0))
        assert dlg._validate() is None

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

    def test_reminder_response_refreshes_immediately(self, qtbot):
        """回归：提醒触发后历史立即可见；弹窗点『标记完成』后任务表立即显示已完成。"""
        from datetime import datetime, timedelta
        from task_reminder.models import fmt
        from task_reminder.ui.main_window import MainWindow
        now = datetime.now()
        tid = mk(name="提醒刷新任务",
                 deadline=fmt(now + timedelta(hours=1)),
                 reminder=fmt(now - timedelta(minutes=1)))
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

        # 模拟轮询触发（真实应用由事件循环执行 singleShot，测试中直接调 pump）
        due = repo.due_for_reminder()
        task = next(t for t in due if t.id == tid)
        hid = repo.mark_triggered(tid)
        win._on_task_due(task, hid)
        win.notifier.pump()

        # 历史页无需切页即已包含本次提醒（结束时间自动跟随当前时刻）
        assert win.history_page.table.rowCount() >= 1
        row0 = [win.history_page.table.item(0, c).text() for c in range(6)]
        assert row0[4] == "未响应"

        # 弹窗出现并点『标记完成』
        assert win.notifier._dialog is not None
        win.notifier._dialog._respond("done")
        assert win.notifier._dialog is None

        # 任务表立即显示已完成（无需手动刷新）
        row_task = next(t for t in win.tasks_page.model.all_tasks() if t.id == tid)
        assert row_task.status == "已完成"
        # 历史页第一行响应列同步为『标记完成』
        assert win.history_page.table.item(0, 4).text() == "标记完成"
