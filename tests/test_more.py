"""补充测试：备份、通用组件、任务页操作、历史/设置页、入口单实例。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QStyleOptionViewItem

from task_reminder import backup, repository as repo
from task_reminder.models import TaskStatus, fmt


def mk(**kw):
    now = datetime.now()
    d = dict(name="补充测试任务", assignee="测试员", content="<b>内容</b>",
             deadline=fmt(now + timedelta(days=1)), reminder=fmt(now + timedelta(hours=1)))
    d.update(kw)
    return repo.add_task(d["name"], d["assignee"], d["content"], d["deadline"], d["reminder"])


# ---------------------------------------------------------------------------
class TestBackup:
    def test_roundtrip(self, tmp_path):
        tid = mk()
        repo.mark_triggered(tid)
        path = str(tmp_path / "backup.json")
        n = backup.export_json(path)
        assert n >= 1

        # 破坏一条数据再恢复
        repo.delete_task(tid)
        t, h = backup.import_json(path)
        assert t >= 1
        assert repo.get_task(tid) is not None

    def test_invalid_format(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text('{"format": "other"}', encoding="utf-8")
        with pytest.raises(ValueError):
            backup.import_json(str(p))

    def test_empty_backup(self, tmp_path):
        path = str(tmp_path / "empty.json")
        assert backup.export_json(path) == 0
        t, h = backup.import_json(path)
        assert (t, h) == (0, 0)


# ---------------------------------------------------------------------------
class TestPaginationBar:
    def test_info_and_navigation(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(450, 2, 200)
        assert bar.page == 2
        # 第 2 页：所有导航按钮均可用
        assert bar.btn_prev.isEnabled()
        assert bar.btn_first.isEnabled()
        assert bar.btn_next.isEnabled()
        bar.btn_next.click()
        assert bar.page == 3
        bar.btn_first.click()
        assert bar.page == 1
        bar.update_info(450, bar.page, 200)    # 宿主收到 page_changed 后刷新状态
        assert not bar.btn_first.isEnabled()   # 第 1 页：首页/上一页禁用
        assert not bar.btn_prev.isEnabled()
        # 越界钳制
        bar._go(99)
        assert bar.page == 3

    def test_page_size_signal(self, qtbot):
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        got = []
        bar.page_size_changed.connect(got.append)
        bar._set_size(50)
        assert got == [50]
        assert bar.size == 50


# ---------------------------------------------------------------------------
class TestDelegates:
    def _index_env(self, qtbot):
        from task_reminder.ui.task_table_model import TaskTableModel
        tid = mk()
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        return m, tid

    def test_status_delegate_paint(self, qtbot):
        from task_reminder.ui.widgets import StatusDelegate
        m, _ = self._index_env(qtbot)
        d = StatusDelegate()
        pix = QPixmap(120, 34)
        pix.fill()
        p = QPainter(pix)
        opt = QStyleOptionViewItem()
        opt.rect = pix.rect()
        d.paint(p, opt, m.index(0, 4))
        p.end()

    def test_action_delegate_hit_test(self, qtbot):
        from PyQt6.QtGui import QMouseEvent
        from task_reminder.ui.widgets import ACTION_DELETE, ACTION_EDIT, ActionDelegate
        m, tid = self._index_env(qtbot)
        d = ActionDelegate()
        got = []
        d.action.connect(lambda a, act: got.append((a, act)))

        opt = QStyleOptionViewItem()
        opt.rect = __import__("PyQt6.QtCore", fromlist=["QRect"]).QRect(0, 0, 132, 34)
        idx = m.index(0, m.column_ids.index("actions"))
        # 编辑按钮中心 (8 + 26, 17) = (34, 17)
        e1 = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(34, 17), QPointF(34, 17),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        assert d.editorEvent(e1, m, opt, idx) is True
        assert got == [(tid, ACTION_EDIT)]
        # 删除按钮中心 (8 + 52 + 8 + 26, 17) = (94, 17)
        e2 = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(94, 17), QPointF(94, 17),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        assert d.editorEvent(e2, m, opt, idx) is True
        assert got[-1] == (tid, ACTION_DELETE)

    def test_deadline_foreground(self, qtbot):
        from task_reminder.ui.widgets import deadline_foreground
        from task_reminder.models import Task
        overdue = Task(id=1, name="t", assignee="a", content="", deadline="2020-01-01 00:00",
                       reminder_time="2020-01-01 00:00", status=TaskStatus.NOT_STARTED)
        assert deadline_foreground(overdue) is not None
        future = Task(id=2, name="t", assignee="a", content="", deadline="2099-01-01 00:00",
                      reminder_time="2099-01-01 00:00", status=TaskStatus.NOT_STARTED)
        assert deadline_foreground(future) is None


# ---------------------------------------------------------------------------
class TestModelMore:
    def test_data_roles(self, qtbot):
        from PyQt6.QtGui import QColor
        from task_reminder import repository as _r
        from task_reminder.ui.task_table_model import TaskTableModel
        _r.add_task("备注任务名称", "张三", "富文本<b>内容</b>", "2026-09-10 10:00",
                    "2026-09-09 09:00", status=TaskStatus.NOT_STARTED, notes="备注X")
        m = TaskTableModel()
        m.set_tasks(repo.all_tasks())
        idx_name = m.index(0, 0)
        assert m.data(idx_name) == "备注任务名称"
        tip = m.data(idx_name, Qt.ItemDataRole.ToolTipRole)
        assert "备注任务名称" in tip
        # 状态列居中
        assert m.data(m.index(0, m.column_ids.index("status")),
                      Qt.ItemDataRole.TextAlignmentRole) == int(Qt.AlignmentFlag.AlignCenter)
        # actions 列 DisplayRole 为空
        assert m.data(m.index(0, m.column_ids.index("actions"))) is None
        assert m.data(m.index(0, m.column_ids.index("notes"))) == "备注X"
        m.set_columns(["name", "status"])
        assert m.columnCount() == 2

    def test_invalid_index(self, qtbot):
        from task_reminder.ui.task_table_model import TaskTableModel
        m = TaskTableModel()
        assert m.data(m.index(-1, 0)) is None
        assert m.task_at(99) is None


# ---------------------------------------------------------------------------
class TestTasksPageOps:
    def test_delete_selected_with_confirm(self, qtbot, monkeypatch):
        tid = mk()
        from task_reminder.ui import tasks_page as tp
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page.view.selectRow(0)
        monkeypatch.setattr(tp, "confirm", staticmethod(lambda *a, **k: True))
        page.on_delete_selected()
        assert repo.get_task(tid) is None

    def test_delete_cancelled(self, qtbot, monkeypatch):
        tid = mk()
        from task_reminder.ui import tasks_page as tp
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page.view.selectRow(0)
        monkeypatch.setattr(tp, "confirm", staticmethod(lambda *a, **k: False))
        page.on_delete_selected()
        assert repo.get_task(tid) is not None

    def test_export_all(self, qtbot, monkeypatch, tmp_path):
        mk()
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        out = tmp_path / "out.xlsx"
        monkeypatch.setattr(page, "_ask_export_scope", lambda n: "all")
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(out), "")))
        msgs = []
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: msgs.append(a)))
        page.on_export()
        assert out.exists()
        assert len(msgs) == 1

    def test_export_selected_and_cancel(self, qtbot, monkeypatch, tmp_path):
        mk(name="选中任务A")
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page.view.selectRow(0)
        # 取消对话框 → 无文件
        monkeypatch.setattr(page, "_ask_export_scope", lambda n: None)
        page.on_export()
        monkeypatch.setattr(page, "_ask_export_scope", lambda n: "selected")
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: ("", "")))
        page.on_export()   # path 为空直接返回
        # 正常导出选中
        out = tmp_path / "sel.xlsx"
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(out), "")))
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        page.on_export()
        assert out.exists()

    def test_set_status_and_action_edit(self, qtbot, monkeypatch):
        tid = mk()
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        page._set_status_multi([page.model.task_at(0)], "进行中")
        assert repo.get_task(tid).status == "进行中"
        page.refresh()
        # 取消编辑对话框不崩溃
        from task_reminder.ui.task_dialog import TaskDialog
        monkeypatch.setattr(TaskDialog, "edit", classmethod(lambda cls, parent, task: False))
        page.on_edit_selected()
        page.view.selectRow(0)
        page.on_edit_selected()

    def test_selected_ids_and_double_click(self, qtbot, monkeypatch):
        tid = mk()
        from task_reminder.ui.tasks_page import TasksPage
        from task_reminder.ui.task_dialog import TaskDialog
        page = TasksPage()
        qtbot.addWidget(page)
        page.view.selectRow(0)
        assert page.selected_ids() == [tid]
        monkeypatch.setattr(TaskDialog, "edit", classmethod(lambda cls, parent, task: False))
        page._on_double_click(page.model.index(0, 0))
        page._on_double_click(page.model.index(0, page.model.column_ids.index("actions")))


# ---------------------------------------------------------------------------
class TestHistoryPage:
    def test_refresh_and_ranges(self, qtbot):
        from PyQt6.QtCore import QDateTime
        from task_reminder.ui.history_page import HistoryPage
        tid = mk()
        hid = repo.mark_triggered(tid)
        page = HistoryPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 1
        page.cmb_quick.setCurrentText("今天")
        page.btn_query.click()
        assert page.table.rowCount() == 1
        page.cmb_quick.setCurrentText("全部")
        page.btn_query.click()
        assert page.table.rowCount() == 1
        # 修改响应
        repo.set_history_response(hid, "标记完成")
        page.refresh()
        assert page.table.item(0, 4).text() == "标记完成"


# ---------------------------------------------------------------------------
class TestSettingsPage:
    def test_load_and_save(self, qtbot):
        from task_reminder import app_config
        from task_reminder.ui.settings_page import SettingsPage
        page = SettingsPage()
        qtbot.addWidget(page)
        page.cmb_theme.setCurrentIndex(1)            # dark → 触发 _apply
        page.spin_font.setValue(15)                  # 触发 _apply
        page.spin_interval.setValue(10)
        page.chk_sound.setChecked(False)
        page.chk_tray_close.setChecked(True)
        page._save()
        assert app_config.get("theme") == "dark"
        assert app_config.get("font_size") == 15
        assert app_config.get("poll_interval") == 10
        assert app_config.get("sound_enabled") is False
        assert app_config.get("tray_close") is True
        # 重新加载
        page2 = SettingsPage()
        qtbot.addWidget(page2)
        assert page2.cmb_theme.currentData() == "dark"
        assert page2.spin_font.value() == 15

    def test_backup_restore_dialogs(self, qtbot, monkeypatch, tmp_path):
        mk()
        from task_reminder.ui import settings_page as sp
        from task_reminder.ui.settings_page import SettingsPage
        page = SettingsPage()
        qtbot.addWidget(page)
        out = tmp_path / "bk.json"
        monkeypatch.setattr(QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(out), "")))
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        page._backup()
        assert out.exists()
        # 恢复（确认弹窗直接放行）
        monkeypatch.setattr(sp, "confirm", staticmethod(lambda *a, **k: True))
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(out), "")))
        page._restore()
        assert len(repo.all_tasks()) == 1
        # 恢复确认弹窗点取消 → 不导入
        monkeypatch.setattr(sp, "confirm", staticmethod(lambda *a, **k: False))
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        page._restore()
        assert len(repo.all_tasks()) == 0
        # 无效文件恢复 → 警告不崩溃
        monkeypatch.setattr(sp, "confirm", staticmethod(lambda *a, **k: True))
        bad = tmp_path / "bad.json"
        bad.write_text('{"format": "x"}', encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(bad), "")))
        page._restore()


# ---------------------------------------------------------------------------
class TestMainModule:
    def test_single_instance_key(self):
        from task_reminder import __version__
        from task_reminder.main import _single_instance_key
        assert _single_instance_key() == f"TaskReminder-{__version__}"

    def test_second_instance_detected(self, qtbot):
        from task_reminder.main import _is_another_running, _single_instance_key
        # 模拟已有实例：先建立 server，下一次检测应返回 True
        first, server1 = _is_another_running()
        assert first is False and server1 is not None and server1.isListening()
        second, _ = _is_another_running()      # 第二次连接到 server1
        assert second is True
        server1.close()
        # server 关闭后可再次监听
        third, server2 = _is_another_running()
        assert third is False
        server2.close()
