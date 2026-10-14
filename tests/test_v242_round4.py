"""第四轮新增测试：TaskTableModel 数据角色、theme 字号钳制、PaginationBar 信号边界。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from task_reminder import repository as repo
from task_reminder.models import Task, TaskStatus, fmt


# ======================================================================
# task_table_model.py — data() 各角色覆盖
# ======================================================================
class TestTaskTableModelDataRoles:
    def _model_with(self, **kw):
        from task_reminder.ui.task_table_model import TaskTableModel
        now = datetime.now()
        defaults = dict(
            name="测试任务", assignee="张三", content="正文内容",
            deadline=fmt(now + timedelta(days=1)),
            reminder_time=fmt(now + timedelta(hours=1)),
            status=TaskStatus.NOT_STARTED,
        )
        defaults.update(kw)
        repo.add_task(**defaults)
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        return m

    def test_content_truncation_80_with_ellipsis(self):
        long = "内" * 100
        m = self._model_with(content=long)
        idx = m.index(0, m.column_ids.index("content"))
        val = m.data(idx)
        assert len(val) == 81  # 80 + ellipsis
        assert val.endswith("…")
        assert "内" in val

    def test_content_under_80_no_ellipsis(self):
        m = self._model_with(content="短内容")
        idx = m.index(0, m.column_ids.index("content"))
        assert m.data(idx) == "短内容"

    def test_content_falls_back_to_notes(self):
        m = self._model_with(content="", notes="备注内容A")
        idx = m.index(0, m.column_ids.index("content"))
        assert m.data(idx) == "备注内容A"

    def test_content_replaces_newlines(self):
        m = self._model_with(content="第一行\n第二行")
        idx = m.index(0, m.column_ids.index("content"))
        assert "\n" not in m.data(idx)
        assert "第一行 第二行" == m.data(idx)

    def test_category_empty_shows_other(self):
        m = self._model_with(category="")
        idx = m.index(0, m.column_ids.index("category"))
        assert m.data(idx) == "其他"

    def test_user_role_status_returns_status(self):
        m = self._model_with(status=TaskStatus.IN_PROGRESS)
        idx = m.index(0, m.column_ids.index("status"))
        assert m.data(idx, Qt.ItemDataRole.UserRole) == TaskStatus.IN_PROGRESS

    def test_user_role_actions_returns_task_id(self):
        m = self._model_with()
        tid = m.all_tasks()[0].id
        idx = m.index(0, m.column_ids.index("actions"))
        assert m.data(idx, Qt.ItemDataRole.UserRole) == tid

    def test_user_role_other_columns_none(self):
        m = self._model_with()
        idx = m.index(0, m.column_ids.index("name"))
        assert m.data(idx, Qt.ItemDataRole.UserRole) is None

    def test_actions_display_role_none(self):
        m = self._model_with()
        idx = m.index(0, m.column_ids.index("actions"))
        assert m.data(idx) is None

    def test_deadline_foreground_red_when_overdue(self):
        past = fmt(datetime.now() - timedelta(days=1))
        m = self._model_with(deadline=past, reminder_time=past,
                             status=TaskStatus.NOT_STARTED)
        idx = m.index(0, m.column_ids.index("deadline"))
        fg = m.data(idx, Qt.ItemDataRole.ForegroundRole)
        assert fg is not None
        assert fg == QColor("#DC2626")

    def test_deadline_foreground_none_when_not_overdue(self):
        m = self._model_with(deadline=fmt(datetime.now() + timedelta(days=1)))
        idx = m.index(0, m.column_ids.index("deadline"))
        assert m.data(idx, Qt.ItemDataRole.ForegroundRole) is None

    def test_reminder_foreground_red_when_overdue(self):
        past = fmt(datetime.now() - timedelta(days=1))
        m = self._model_with(deadline=past, reminder_time=past,
                             status=TaskStatus.NOT_STARTED)
        idx = m.index(0, m.column_ids.index("reminder_time"))
        assert m.data(idx, Qt.ItemDataRole.ForegroundRole) is not None

    def test_status_text_alignment_center(self):
        m = self._model_with()
        idx = m.index(0, m.column_ids.index("status"))
        assert m.data(idx, Qt.ItemDataRole.TextAlignmentRole) == int(Qt.AlignmentFlag.AlignCenter)

    def test_category_text_alignment_center(self):
        m = self._model_with()
        idx = m.index(0, m.column_ids.index("category"))
        assert m.data(idx, Qt.ItemDataRole.TextAlignmentRole) == int(Qt.AlignmentFlag.AlignCenter)

    def test_name_no_alignment(self):
        m = self._model_with()
        idx = m.index(0, m.column_ids.index("name"))
        assert m.data(idx, Qt.ItemDataRole.TextAlignmentRole) is None

    def test_tooltip_contains_key_fields(self):
        m = self._model_with(name="提示任务", notes="备注文本")
        idx = m.index(0, m.column_ids.index("name"))
        tip = m.data(idx, Qt.ItemDataRole.ToolTipRole)
        assert "提示任务" in tip
        assert "张三" in tip
        assert "备注文本" in tip

    def test_header_vertical_returns_none(self):
        m = self._model_with()
        assert m.headerData(0, Qt.Orientation.Vertical) is None

    def test_set_columns_changes_order(self):
        m = self._model_with()
        m.set_columns(["status", "name"])
        assert m.column_ids == ["status", "name"]
        assert m.columnCount() == 2
        assert m.headerData(0, Qt.Orientation.Horizontal) == "状态"


# ======================================================================
# theme.py — 字号钳制与主题色
# ======================================================================
class TestThemeQss:
    def test_font_clamped_below_11(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light", font_size=5)
        assert "font-size: 11px" in qss
        assert "font-size: 5px" not in qss

    def test_font_clamped_above_22(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light", font_size=50)
        assert "font-size: 22px" in qss

    def test_font_within_range_unchanged(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light", font_size=16)
        assert "font-size: 16px" in qss

    def test_dark_theme_has_dark_background(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("dark")
        assert "#0F172A" in qss
        assert "#1E293B" in qss

    def test_light_theme_has_light_background(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light")
        assert "#F5F7FA" in qss
        assert "#FFFFFF" in qss

    def test_derived_font_sizes(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light", font_size=14)
        # FS_S = 12, FS_T = 17, FS_XT = 22
        assert "12px" in qss
        assert "17px" in qss
        assert "22px" in qss

    def test_check_png_path_present(self):
        from task_reminder.ui.theme import theme_qss
        qss = theme_qss("light")
        assert "check.png" in qss
        assert "{CHECK_PNG}" not in qss

    def test_apply_theme_sets_stylesheet(self, qtbot):
        from PyQt6.QtWidgets import QApplication
        from task_reminder.ui.theme import apply_theme
        app = QApplication.instance()
        apply_theme(app, "light", 15)
        sheet = app.styleSheet()
        assert "15px" in sheet
        assert "#F5F7FA" in sheet


# ======================================================================
# widgets.py — PaginationBar 信号边界 & ActionDelegate 越界
# ======================================================================
class TestPaginationBarEdgeCases:
    def test_go_same_page_no_signal(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(100, 1, 20)
        fired = []
        bar.page_changed.connect(fired.append)
        bar._go(1)  # same page
        assert fired == []

    def test_go_clamps_below_one(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(100, 2, 20)
        fired = []
        bar.page_changed.connect(fired.append)
        bar._go(-5)
        assert bar.page == 1
        assert fired == [1]

    def test_go_clamps_above_pages(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(100, 1, 20)  # 5 pages
        fired = []
        bar.page_changed.connect(fired.append)
        bar._go(999)
        assert bar.page == 5
        assert fired == [5]

    def test_update_info_last_page_disables_next(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(40, 2, 20)  # 2 pages, on last
        assert bar.btn_prev.isEnabled()
        assert not bar.btn_next.isEnabled()

    def test_update_info_first_page_disables_prev(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(40, 1, 20)
        assert not bar.btn_prev.isEnabled()
        assert bar.btn_next.isEnabled()

    def test_update_info_zero_total(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(0, 1, 20)
        assert "共 0 条" in bar.lbl_info.text()
        assert not bar.btn_prev.isEnabled()
        assert not bar.btn_next.isEnabled()


class TestActionDelegateMiss:
    def test_click_outside_buttons_returns_false(self, qtbot):
        from PyQt6.QtCore import QPointF, QRect
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtWidgets import QStyleOptionViewItem
        from task_reminder.ui.task_table_model import TaskTableModel
        from task_reminder.ui.widgets import ActionDelegate
        now = datetime.now()
        repo.add_task("点击测试", "张三", "",
                      fmt(now + timedelta(days=1)), fmt(now + timedelta(hours=1)))
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        d = ActionDelegate()
        got = []
        d.action.connect(lambda *a: got.append(a))
        opt = QStyleOptionViewItem()
        opt.rect = QRect(0, 0, 132, 34)
        idx = m.index(0, m.column_ids.index("actions"))
        # 点击两按钮之间的间隙 (8+52=60, 间隙约 60~68)
        e = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(64, 17),
                        QPointF(64, 17), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        assert d.editorEvent(e, m, opt, idx) is False
        assert got == []
