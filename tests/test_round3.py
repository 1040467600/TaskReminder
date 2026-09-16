"""第三轮补充测试：配置持久化往返 / 损坏配置兜底 / 真实交互事件 /
提醒链路端到端 / 数据完整性 / 输入校验加固。

对应 docs/test_cases.md 第 9 节（58 条用例）。

三条铁律（源自 v2.0.10 / v2.0.11 两个真实回归 bug 的教训）：
1. 持久化必须测往返：写入 → 新建实例（模拟重启）→ 断言恢复，禁止只断言默认值。
2. UI 必须用真实事件：qtbot.keyClicks / mouseClick，锚点是内容/数据而非信号发射。
3. 负向必须固化期望：损坏配置 / 非法输入明确断言"兜底 + 不崩溃"。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication

from task_reminder import app_config, backup, db, excel_io, repository as repo
from task_reminder.models import Task, TaskStatus, fmt, html_to_plain, parse


def mk(**kw):
    """创建一条测试任务，返回 task_id。"""
    now = datetime.now()
    d = dict(name="三轮测试任务", assignee="测试员", content="<b>内容</b>",
             deadline=fmt(now + timedelta(days=1)), reminder=fmt(now + timedelta(hours=1)),
             status=TaskStatus.NOT_STARTED, notes="")
    d.update(kw)
    return repo.add_task(d["name"], d["assignee"], d["content"], d["deadline"],
                         d["reminder"], d["status"], d["notes"])


def make_tasks(n: int, prefix: str = "任务") -> None:
    """按序号创建 n 条任务（任务00…任务{n-1}，后建的更新）。"""
    now = datetime.now()
    for i in range(n):
        repo.add_task(f"{prefix}{i:02d}", "测试员", f"内容{i}",
                      fmt(now + timedelta(days=1)), fmt(now + timedelta(hours=1)),
                      TaskStatus.NOT_STARTED, "")


def first_row_name(page) -> str:
    """表格首行任务名（内容锚点）。"""
    m = page.model
    if m.rowCount() == 0:
        return "<empty>"
    idx = m.index(0, m.column_ids.index("name"))
    return m.data(idx, Qt.ItemDataRole.DisplayRole)


def make_page(qtbot):
    from task_reminder.ui.tasks_page import TasksPage
    page = TasksPage()
    qtbot.addWidget(page)
    return page


# ===========================================================================
# 9.1.1 配置持久化往返（12 条）
# ===========================================================================
class TestConfigPersistenceRoundTrip:
    """操作/落库 → 新建实例（模拟重启）→ 断言 UI 反映保存值。"""

    def test_window_geometry_roundtrip(self, qtbot):
        """真实保存（_window_state_json）→ 新 MainWindow 几何精确恢复。"""
        from task_reminder.ui.main_window import MainWindow
        win1 = MainWindow()
        qtbot.addWidget(win1)
        win1.setGeometry(80, 90, 1100, 750)
        app_config.set("window_state", win1._window_state_json())
        win2 = MainWindow()
        qtbot.addWidget(win2)
        g = win2.geometry()
        assert (g.x(), g.y(), g.width(), g.height()) == (80, 90, 1100, 750)

    def test_window_maximized_roundtrip(self, qtbot):
        """最大化状态 → 新 MainWindow 恢复最大化。"""
        from task_reminder.ui.main_window import MainWindow
        win1 = MainWindow()
        qtbot.addWidget(win1)
        win1.setWindowState(Qt.WindowState.WindowMaximized)
        app_config.set("window_state", win1._window_state_json())
        win2 = MainWindow()
        qtbot.addWidget(win2)
        assert win2.isMaximized()

    def test_sort_state_roundtrip(self, qtbot):
        """表头点击排序（deadline 升序）→ 新页面恢复排序键/方向。"""
        make_tasks(3)
        page1 = make_page(qtbot)
        logical = page1.model.column_ids.index("deadline")
        page1._on_header_clicked(logical)          # 程序化表头点击 → asc
        assert page1.sort_key == "deadline" and page1.sort_dir == "asc"
        page2 = make_page(qtbot)                   # 新实例 = 模拟重启
        assert page2.sort_key == "deadline" and page2.sort_dir == "asc"

    def test_column_order_roundtrip(self, qtbot):
        """拖拽列序（name 移到视觉第 3 位）→ 新实例恢复相同视觉列序。"""
        page1 = make_page(qtbot)
        header1 = page1.view.horizontalHeader()
        header1.moveSection(0, 2)                  # sectionMoved → 自动保存
        page2 = make_page(qtbot)
        # 恢复语义：列配置按保存的视觉顺序应用 → model.column_ids 反映列序
        assert page2.model.column_ids[0] == "content"
        assert page2.model.column_ids[2] == "name"

    def test_column_visibility_roundtrip(self, qtbot):
        """隐藏 content 列 → 新实例该列仍隐藏。"""
        page1 = make_page(qtbot)
        logical = page1.model.column_ids.index("content")
        page1._toggle_column(logical, False)       # 隐藏并保存
        page2 = make_page(qtbot)
        header2 = page2.view.horizontalHeader()
        logical2 = page2.model.column_ids.index("content")
        assert header2.isSectionHidden(logical2)

    def test_column_width_roundtrip(self, qtbot):
        """调列宽 200 → 下一次保存事件落库 → 新实例列宽≈200。"""
        page1 = make_page(qtbot)
        header1 = page1.view.horizontalHeader()
        logical = page1.model.column_ids.index("content")
        header1.resizeSection(logical, 200)
        page1._save_states()                       # 真实流程中由后续保存事件触发
        page2 = make_page(qtbot)
        header2 = page2.view.horizontalHeader()
        logical2 = page2.model.column_ids.index("content")
        assert header2.sectionSize(logical2) >= 190

    def test_page_size_roundtrip(self, qtbot):
        """每页条数 50 → 新实例 pager.size==50 并按 50 条/页查询。"""
        app_config.set("page_size", 50)
        page = make_page(qtbot)
        assert page.pager.size == 50

    def test_theme_roundtrip(self, qtbot):
        """切深色主题 → 新设置页下拉框反映 dark。"""
        app_config.set("theme", "dark")
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.cmb_theme.currentData() == "dark"

    def test_sound_enabled_roundtrip(self, qtbot):
        """关声音 → 新设置页复选框未勾选。"""
        app_config.set("sound_enabled", False)
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.chk_sound.isChecked() is False

    def test_sound_file_roundtrip(self, qtbot):
        """自定义音效路径 → 新设置页下拉框选中该自定义项。"""
        app_config.set("sound_file", "C:/tmp/my_sound.wav")
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.cmb_sound.currentData() == "C:/tmp/my_sound.wav"

    def test_poll_interval_roundtrip(self, qtbot):
        """轮询间隔 10s → 新设置页 spin==10，新服务定时器间隔==10000ms。"""
        app_config.set("poll_interval", 10)
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.spin_interval.value() == 10
        from task_reminder.reminder_service import ReminderService
        service = ReminderService()
        service.apply_interval()
        assert service._timer.interval() == 10_000

    def test_tray_close_roundtrip(self, qtbot):
        """tray_close=False → 设置页未勾选；主窗口 closeEvent 直接接受并保存几何。"""
        app_config.set("tray_close", False)
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.chk_tray_close.isChecked() is False
        from task_reminder.ui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.setGeometry(50, 60, 900, 700)
        ev = QCloseEvent()
        win.closeEvent(ev)
        assert ev.isAccepted()
        assert app_config.get("window_state")      # 关闭时保存了窗口几何


# ===========================================================================
# 9.1.2 损坏配置兜底（6 条）
# ===========================================================================
class TestConfigCorruptFallback:
    """损坏/越界配置 → 兜底默认值且不崩溃（防止异常被吞导致静默失效）。"""

    def test_window_state_corrupt_fallback(self, qtbot):
        """窗口状态坏 JSON → 默认几何 1000×680，不崩溃。"""
        app_config.set("window_state", "{broken")
        from task_reminder.ui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        g = win.geometry()
        assert g.width() == 1000 and g.height() == 680

    def test_sort_state_corrupt_fallback(self, qtbot):
        """排序状态坏 JSON → 默认 created_at，方向为默认（''）。"""
        app_config.set("sort_state", "{bad")
        page = make_page(qtbot)
        assert page.sort_key == "created_at" and page.sort_dir == ""

    def test_column_state_corrupt_fallback(self, qtbot):
        """列配置坏 JSON → 默认列序，name 列可见。"""
        app_config.set("column_state", "[oops")
        page = make_page(qtbot)
        from task_reminder.ui.widgets import COLUMNS
        assert page.model.column_ids == [c[0] for c in COLUMNS]
        assert not page.view.horizontalHeader().isSectionHidden(0)

    def test_page_size_invalid_fallback(self, qtbot):
        """每页条数 0 / 负数 / 非数字 → 兜底可用值，构造不崩溃。"""
        app_config.set("page_size", 0)
        page1 = make_page(qtbot)
        assert page1.pager.size == 1
        app_config.set("page_size", -5)
        page2 = make_page(qtbot)
        assert page2.pager.size == 1
        app_config.set("page_size", "abc")
        page3 = make_page(qtbot)
        assert page3.pager.size == 200             # 非数字兜底默认 200
        page3.refresh()                            # 查询链路同样不崩

    def test_poll_interval_out_of_range_clamp(self, qtbot):
        """轮询间隔 0 / 999 → 钳制到 [1,60] 秒。"""
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", 0)
        s1 = ReminderService()
        s1.apply_interval()
        assert s1._timer.interval() == 1_000
        app_config.set("poll_interval", 999)
        s2 = ReminderService()
        s2.apply_interval()
        assert s2._timer.interval() == 60_000

    def test_theme_unknown_value_fallback(self, qtbot):
        """未知主题值 → 设置页回退 light，apply_theme 不抛异常。"""
        app_config.set("theme", "purple")
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        assert sp.cmb_theme.currentData() == "light"
        from task_reminder.ui.theme import apply_theme
        apply_theme(QApplication.instance(), "purple", 13)   # 不崩溃即通过


# ===========================================================================
# 9.2.1 分页真实交互（7 条）
# ===========================================================================
class TestPaginationRealInteraction:
    """真实键盘/鼠标事件驱动分页，断言锚点是表格内容。"""

    def _page12(self, qtbot):
        make_tasks(12)                             # 12 条 / 每页 5 → 3 页
        page = make_page(qtbot)
        page.pager.size = 5
        page.refresh()
        page.show()
        qtbot.wait(30)
        return page

    def test_prev_next_changes_rows(self, qtbot):
        """mouseClick 下一页×2 → 首行内容逐页变化。"""
        page = self._page12(qtbot)
        p1_first = first_row_name(page)
        qtbot.mouseClick(page.pager.btn_next, Qt.MouseButton.LeftButton)
        qtbot.wait(20)
        p2_first = first_row_name(page)
        assert page.page_no == 2 and p2_first != p1_first
        qtbot.mouseClick(page.pager.btn_next, Qt.MouseButton.LeftButton)
        qtbot.wait(20)
        assert page.page_no == 3 and first_row_name(page) != p2_first

    def test_keyboard_enter_jump(self, qtbot):
        """键盘输入页码 + 回车 → 跳到目标页（内容锚点）。"""
        page = self._page12(qtbot)
        sp = page.pager.spin_page
        sp.setFocus()
        sp.lineEdit().selectAll()
        qtbot.keyClicks(sp, "3")
        qtbot.keyClick(sp, Qt.Key.Key_Return)
        qtbot.wait(20)
        assert page.page_no == 3 and page.model.rowCount() == 2

    def test_spinbox_arrow_buttons(self, qtbot):
        """spinbox 上下箭头改值 → editingFinished（失焦）后跳页。"""
        page = self._page12(qtbot)
        sp = page.pager.spin_page
        qtbot.keyClick(sp, Qt.Key.Key_Up)          # 上箭头：1 → 2
        qtbot.wait(20)
        assert sp.value() == 2 and page.page_no == 1   # 未失焦，尚未跳页
        sp.editingFinished.emit()                  # 失焦兜底路径
        qtbot.wait(20)
        assert page.page_no == 2 and first_row_name(page) != "任务11"

    def test_page_size_menu_click(self, qtbot):
        """每页条数菜单动作触发 → 每页行数变化并落库。"""
        make_tasks(60)
        page = make_page(qtbot)                    # 默认 200 → 全量 60 行
        target = next(a for a in page.pager._menu.actions() if a.text() == "每页 50")
        target.trigger()                           # 真实菜单项 triggered 信号
        qtbot.wait(20)
        assert page.model.rowCount() == 50
        assert app_config.get("page_size") == 50

    def test_first_page_prev_disabled(self, qtbot):
        """第 1 页 → 上一页禁用。"""
        page = self._page12(qtbot)
        assert page.page_no == 1
        assert not page.pager.btn_prev.isEnabled()

    def test_last_page_next_disabled(self, qtbot):
        """末页 → 下一页禁用、上一页可用。"""
        page = self._page12(qtbot)
        qtbot.mouseClick(page.pager.btn_next, Qt.MouseButton.LeftButton)
        qtbot.wait(10)
        qtbot.mouseClick(page.pager.btn_next, Qt.MouseButton.LeftButton)
        qtbot.wait(10)
        assert page.page_no == 3
        assert not page.pager.btn_next.isEnabled()
        assert page.pager.btn_prev.isEnabled()

    def test_jump_then_refresh_keeps_page(self, qtbot):
        """跳到第 2 页后新增任务并 refresh → 仍在第 2 页且不为空。"""
        page = self._page12(qtbot)
        sp = page.pager.spin_page
        sp.setValue(2)
        sp.editingFinished.emit()
        qtbot.wait(20)
        assert page.page_no == 2
        mk(name="新增任务")                         # 数据变化 → 3 页仍成立
        page.refresh()
        assert page.page_no == 2 and page.model.rowCount() == 5


# ===========================================================================
# 9.2.2 搜索栏真实交互（4 条）
# ===========================================================================
class TestSearchBarRealInteraction:
    def _page(self, qtbot):
        repo.add_task("苹果购买清单", "甲", "内容", fmt(datetime.now() + timedelta(days=1)),
                      fmt(datetime.now() + timedelta(hours=1)), TaskStatus.NOT_STARTED, "")
        repo.add_task("香蕉计划", "甲", "内容", fmt(datetime.now() + timedelta(days=1)),
                      fmt(datetime.now() + timedelta(hours=1)), TaskStatus.IN_PROGRESS, "")
        repo.add_task("橙子报告", "乙", "内容", fmt(datetime.now() + timedelta(days=1)),
                      fmt(datetime.now() + timedelta(hours=1)), TaskStatus.DONE, "")
        page = make_page(qtbot)
        page.show()
        qtbot.wait(30)
        return page

    def test_keyword_enter_filters(self, qtbot):
        """关键词键入 → 防抖后列表只含匹配项。

        注：QTest.keyClicks 发送 CJK 字符在 offscreen 下会触发 0xC0000409
        崩溃（无键码映射的平台限制），故文本输入统一走 QLineEdit.insert()
        ——真实键入/IME 最终产生的就是 textChanged 路径。
        """
        page = self._page(qtbot)
        sp = page.search.edit_keyword
        sp.clear()
        sp.insert("苹果")
        qtbot.wait(450)                            # 覆盖 300ms 防抖
        assert page.model.rowCount() == 1
        assert "苹果" in first_row_name(page)

    def test_clear_button_restores(self, qtbot):
        """点重置按钮 → 列表恢复全量 3 条。"""
        page = self._page(qtbot)
        page.search.edit_keyword.setText("苹果")
        qtbot.wait(450)
        assert page.model.rowCount() == 1
        page.search.btn_reset.click()
        qtbot.wait(450)
        assert page.model.rowCount() == 3

    def test_status_checkbox_click_filters(self, qtbot):
        """mouseClick 取消勾选"已完成" → 表格不再显示已完成任务。"""
        page = self._page(qtbot)
        page.search.btn_advanced.setChecked(True)          # 展开高级面板
        cb = page.search.chk_status["已完成"]
        qtbot.mouseClick(cb, Qt.MouseButton.LeftButton)
        qtbot.wait(450)
        names = [first_row_name(page)]
        assert page.model.rowCount() == 2                  # 橙子报告（已完成）被过滤
        statuses = set()
        for r in range(page.model.rowCount()):
            idx = page.model.index(r, page.model.column_ids.index("status"))
            statuses.add(page.model.data(idx, Qt.ItemDataRole.DisplayRole))
        assert statuses == {"未开始", "进行中"}

    def test_keyword_live_change(self, qtbot):
        """改关键词重新搜索 → 结果随词变化。"""
        page = self._page(qtbot)
        sp = page.search.edit_keyword
        sp.insert("苹果")
        qtbot.wait(450)
        first1 = first_row_name(page)
        sp.clear()
        sp.insert("橙子")
        qtbot.wait(450)
        assert page.model.rowCount() == 1
        first2 = first_row_name(page)
        assert first1 != first2 and "橙子" in first2


# ===========================================================================
# 9.2.3 任务对话框真实交互（4 条）
# ===========================================================================
class TestTaskDialogRealInteraction:
    def test_name_field_saved(self, qtbot):
        """名称框输入 + 保存 → DB 名称与输入一致（insert 触发 textChanged）。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.insert("键盘输入的任务名")
        dlg.edit_assignee.setText("张三")
        dlg._on_save()
        from PyQt6.QtWidgets import QDialog
        assert dlg.result() == QDialog.DialogCode.Accepted
        task = repo.get_task(dlg.task_id)
        assert task.name == "键盘输入的任务名"

    def test_status_combo_change(self, qtbot):
        """状态下拉选"进行中" → 保存后状态落库为进行中。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("状态切换任务")
        dlg.edit_assignee.setText("张三")
        dlg.cmb_status.setCurrentText(TaskStatus.IN_PROGRESS)
        dlg._on_save()
        assert repo.get_task(dlg.task_id).status == TaskStatus.IN_PROGRESS

    def test_assignee_completer(self, qtbot):
        """执行人框键入触发补全：completer 候选含历史执行人。"""
        mk(assignee="张三丰")                       # 制造历史执行人
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        completer = dlg.edit_assignee.completer()
        assert completer is not None
        dlg.edit_assignee.insert("张")             # textChanged → completer 更新
        qtbot.wait(50)
        assert completer.completionPrefix() == "张"
        assert completer.completionCount() >= 1

    def test_deadline_date_edit(self, qtbot):
        """日期控件改截止时间 → 保存后 deadline 落库为所选时间。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("日期修改任务")
        dlg.edit_assignee.setText("张三")
        target = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=3)
        dlg.dt_deadline.setDateTime(QDateTime(target))
        dlg._on_save()
        saved = parse(repo.get_task(dlg.task_id).deadline)
        assert saved == target


# ===========================================================================
# 9.2.4 设置页真实交互（4 条）
# ===========================================================================
class TestSettingsPageRealInteraction:
    def _page(self, qtbot):
        from task_reminder.ui.settings_page import SettingsPage
        sp = SettingsPage()
        qtbot.addWidget(sp)
        return sp

    def test_page_size_spin_change(self, qtbot):
        """每页条数选 100 → 落库 page_size==100。"""
        sp = self._page(qtbot)
        sp.cmb_page_size.setCurrentIndex(sp.cmb_page_size.findData(100))
        assert app_config.get("page_size") == 100

    def test_sound_checkbox_toggle(self, qtbot):
        """点击声音复选框 → sound_enabled 翻转落库（click 走按钮真实点击路径）。"""
        sp = self._page(qtbot)
        sp.show()
        qtbot.wait(30)
        assert sp.chk_sound.isChecked() is True    # 默认开
        sp.chk_sound.click()                       # 等价鼠标点击，offscreen 下确定性触发
        assert app_config.get("sound_enabled") is False

    def test_theme_combo_select_dark(self, qtbot):
        """下拉选深色 → theme_changed 发射且落库 dark。"""
        sp = self._page(qtbot)
        fired = []
        sp.theme_changed.connect(lambda t, f: fired.append(t))
        sp.cmb_theme.setCurrentIndex(sp.cmb_theme.findData("dark"))
        assert fired == ["dark"]
        assert app_config.get("theme") == "dark"

    def test_poll_spin_clamped(self, qtbot):
        """轮询 spin 输入 999 → 控件钳到上限 60 并落库 60。"""
        sp = self._page(qtbot)
        sp.spin_interval.setValue(999)
        assert sp.spin_interval.value() == 60
        assert app_config.get("poll_interval") == 60


# ===========================================================================
# 9.3.1 提醒链路端到端（6 条）
# ===========================================================================
class TestReminderFlowE2E:
    """tick → task_due_batch → notify_batch → pump → 弹窗响应 → DB 终态。"""

    def _wire(self):
        from task_reminder.notifier import Notifier
        from task_reminder.reminder_service import ReminderService
        service = ReminderService()
        notifier = Notifier()
        service.task_due_batch.connect(notifier.notify_batch)
        return service, notifier

    def _due_task(self, **kw):
        now = datetime.now()
        d = dict(name="到期任务", reminder=fmt(now - timedelta(minutes=1)))
        d.update(kw)
        return mk(**d)

    def _history_for(self, tid):
        logs, total = repo.list_history(page=1, page_size=100)
        return [lg for lg in logs if lg.task_id == tid]

    def test_due_creates_dialog_and_log(self, qtbot):
        """到期全链路：tick → 历史记录 + 弹窗创建。"""
        tid = self._due_task()
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        logs = self._history_for(tid)
        assert len(logs) == 1 and logs[0].response == ""
        assert notifier._dialog is not None
        notifier._dialog._respond("close")         # 清理弹窗

    def test_done_updates_status(self, qtbot):
        """点"标记完成" → 任务已完成 + 历史响应 done。"""
        tid = self._due_task()
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        notifier._dialog._respond("done")
        assert repo.get_task(tid).status == TaskStatus.DONE
        logs = self._history_for(tid)
        assert logs[0].response == "done"

    def test_snooze_advances_reminder(self, qtbot):
        """稍后提醒 15 分钟 → reminder_time 后移 ≥14 分钟且可再次触发。"""
        tid = self._due_task()
        old_r = parse(repo.get_task(tid).reminder_time)
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        notifier._dialog._respond("snooze", minutes=15)
        t = repo.get_task(tid)
        new_r = parse(t.reminder_time)
        assert (new_r - old_r).total_seconds() >= 14 * 60
        assert t.triggered == 0                    # 允许再次触发

    def test_close_keeps_status(self, qtbot):
        """点"关闭" → 状态不变，历史响应 close。"""
        tid = self._due_task()
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        notifier._dialog._respond("close")
        assert repo.get_task(tid).status == TaskStatus.NOT_STARTED
        assert self._history_for(tid)[0].response == "close"

    def test_same_day_no_duplicate(self, qtbot):
        """同日同任务不重复触发：第二次 tick 不再入队/记录。"""
        tid = self._due_task()
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        notifier._dialog._respond("close")
        assert len(self._history_for(tid)) == 1
        service.tick()                             # triggered=1 → 不再到期
        notifier.pump()
        assert notifier.pending_count() == 0
        assert notifier._dialog is None
        assert len(self._history_for(tid)) == 1    # 仍是 1 条

    def test_cross_day_reset_retrigger(self, qtbot):
        """跨日重置 → triggered 归零后可再次触发（历史新增 1 条）。"""
        yesterday = fmt(datetime.now() - timedelta(days=1))
        tid = self._due_task(reminder=yesterday)   # 提醒时间在昨日
        service, notifier = self._wire()
        service.tick()
        notifier.pump()
        notifier._dialog._respond("close")
        assert len(self._history_for(tid)) == 1
        service.tick()                             # 未重置前不再触发
        notifier.pump()
        assert len(self._history_for(tid)) == 1
        assert repo.reset_triggered_for_new_day() == 1
        service.tick()                             # 重置后再次触发
        notifier.pump()
        assert notifier._dialog is not None
        assert len(self._history_for(tid)) == 2
        notifier._dialog._respond("close")


# ===========================================================================
# 9.3.2 数据变化联动（3 条）
# ===========================================================================
class TestDataChangeChain:
    def test_filter_updates_statusbar(self, qtbot):
        """搜索过滤 → 表格只剩匹配项；状态栏"共 N 条"显示全量总数。"""
        from task_reminder.ui.main_window import MainWindow
        mk(name="普通任务甲")
        mk(name="普通任务乙")
        mk(name="特别任务")
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()
        qtbot.wait(30)
        page = win.tasks_page
        page.search.edit_keyword.setText("特别")
        qtbot.wait(450)
        assert page.model.rowCount() == 1
        win._update_next_status()
        assert win.status_db.text() == "共 3 条任务"

    def test_complete_refreshes_dashboard(self, qtbot):
        """任务完成 → 看板"已完成"卡片 +1。"""
        from task_reminder.ui.main_window import MainWindow
        tid = mk(name="待完成任务")
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.dashboard_page.card_done.lbl_value.text() == "0"
        repo.set_status(tid, TaskStatus.DONE)
        win.tasks_page.refresh()
        win.tasks_page.data_changed.emit()         # 与真实编辑完成后的信号一致
        assert win.dashboard_page.card_done.lbl_value.text() == "1"
        assert win.dashboard_page.card_total.lbl_value.text() == "1"

    def test_delete_last_on_page_backs_off(self, qtbot):
        """末页最后一条被删 → refresh 自动回退上一页，不空白。"""
        make_tasks(7)                              # 7 条 / 每页 3 → 3 页（末页 1 条）
        page = make_page(qtbot)
        page.pager.size = 3
        page.refresh()
        page.pager.spin_page.setValue(3)           # 跳到末页
        page.pager.spin_page.editingFinished.emit()
        qtbot.wait(20)
        assert page.page_no == 3 and page.model.rowCount() == 1
        last_row_task = page.model.task_at(0)
        repo.delete_task(last_row_task.id)         # 删除末页唯一一条
        page.refresh()
        assert page.page_no == 2                   # 自动回退
        assert page.model.rowCount() == 3          # 上一页满页显示


# ===========================================================================
# 9.4.1 备份恢复数据完整性（3 条）
# ===========================================================================
class TestBackupRestoreIntegrity:
    def test_restore_all_fields_match(self, qtbot, tmp_path):
        """备份→清库→恢复：任务逐字段与原始一致（含富文本/触发标记）。"""
        now = datetime.now()
        tid = repo.add_task("完整性任务", "王五", "<b>加粗内容</b><br>第二行",
                            fmt(now + timedelta(days=2)), fmt(now + timedelta(hours=2)),
                            TaskStatus.IN_PROGRESS, "备注信息")
        original = repo.get_task(tid)
        path = str(tmp_path / "backup.json")
        assert backup.export_json(path) == 1
        with db.transaction() as c:                # 清库
            c.execute("DELETE FROM tasks")
            c.execute("DELETE FROM reminder_history")
        n_tasks, _ = backup.import_json(path)
        assert n_tasks == 1
        restored = repo.get_task(tid)
        for field in ("name", "assignee", "content", "deadline", "reminder_time",
                      "status", "notes", "triggered", "created_at", "updated_at"):
            assert getattr(restored, field) == getattr(original, field), field
        assert restored.content_plain == html_to_plain(original.content)

    def test_restore_history_with_response(self, qtbot, tmp_path):
        """含用户响应的提醒历史 → 备份恢复后条数与 response 完整。"""
        tid = mk(name="历史完整性任务")
        hid = repo.mark_triggered(tid)
        repo.set_history_response(hid, "snooze")
        path = str(tmp_path / "backup.json")
        backup.export_json(path)
        with db.transaction() as c:
            c.execute("DELETE FROM tasks")
            c.execute("DELETE FROM reminder_history")
        _, n_hist = backup.import_json(path)
        assert n_hist == 1
        logs, total = repo.list_history(page=1, page_size=100)
        assert total == 1
        assert logs[0].id == hid and logs[0].task_id == tid
        assert logs[0].response == "snooze" and logs[0].responded_at

    def test_restore_settings(self, qtbot, tmp_path):
        """设置不属于备份内容但恢复操作不影响现有设置（完整性）。"""
        app_config.set("poll_interval", 13)
        app_config.set("sound_file", "C:/x.wav")
        path = str(tmp_path / "backup.json")
        backup.export_json(path)
        with db.transaction() as c:
            c.execute("DELETE FROM tasks")
            c.execute("DELETE FROM reminder_history")
        backup.import_json(path)
        assert app_config.get("poll_interval") == 13
        assert app_config.get("sound_file") == "C:/x.wav"


# ===========================================================================
# 9.4.2 Excel 导入导出完整性（3 条）
# ===========================================================================
class TestExcelIntegrity:
    def test_chinese_richtext_roundtrip(self, qtbot, tmp_path):
        """中文富文本导出→读回：纯文本内容一致。"""
        content = "<b>中文加粗</b><br>第二行"
        mk(name="富文本任务", content=content)
        task = repo.list_tasks(page=1, page_size=10)[0][0]
        path = str(tmp_path / "out.xlsx")
        assert excel_io.export_tasks(path, [task]) == 1
        rows = excel_io.read_rows(path)
        assert len(rows) == 1
        expected = html_to_plain(content)
        assert rows[0]["content"] == expected
        assert "中文加粗" in rows[0]["content"] and "第二行" in rows[0]["content"]

    def test_empty_fields_handled(self, qtbot, tmp_path):
        """空备注行正常导入；缺截止时间的行报错但不崩溃。"""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(excel_io.HEADERS)
        ws.append(["空备注任务", "张三", "内容", "2026-10-01 10:00", "2026-10-01 09:00",
                   "未开始", "", ""])
        ws.append(["缺截止任务", "李四", "内容", "", "2026-10-01 09:00", "未开始", "", ""])
        path = str(tmp_path / "in.xlsx")
        wb.save(path)
        report = excel_io.import_tasks(path)
        assert report.total == 2
        assert report.added == 1 and len(report.errors) == 1
        # 错误信息格式："第 3 行：截止时间缺失或格式无法识别"（含行号与原因）
        assert "第 3 行" in report.errors[0] and "截止时间" in report.errors[0]

    def test_long_name_50_roundtrip(self, qtbot, tmp_path):
        """50 字名称导出→读回：完整保留无截断。"""
        name = "测" * 50
        mk(name=name)
        task = repo.list_tasks(page=1, page_size=10)[0][0]
        path = str(tmp_path / "out.xlsx")
        excel_io.export_tasks(path, [task])
        rows = excel_io.read_rows(path)
        assert rows[0]["name"] == name
        assert len(rows[0]["name"]) == 50


# ===========================================================================
# 9.5 输入校验与安全加固（6 条）
# ===========================================================================
class TestValidationHardening:
    def test_reminder_after_deadline_rejected(self):
        """提醒晚于截止 → ValidationError。"""
        now = datetime.now()
        with pytest.raises(repo.ValidationError, match="提醒时间"):
            repo.validate_task("任务", "执行人", "内容",
                               fmt(now + timedelta(days=1)), fmt(now + timedelta(days=2)))

    def test_reminder_equals_deadline_rejected(self):
        """提醒等于截止 → ValidationError（必须严格早于）。"""
        t = fmt(datetime.now() + timedelta(days=1))
        with pytest.raises(repo.ValidationError, match="提醒时间"):
            repo.validate_task("任务", "执行人", "内容", t, t)

    def test_script_tag_in_content_stored_safe(self):
        """content 含 <script> → 存储不执行，纯文本剥离脚本内容。"""
        tid = mk(name="脚本注入任务", content="<script>alert(1)</script><b>正文</b>")
        task = repo.get_task(tid)
        assert "alert(1)" not in task.content_plain
        assert "正文" in task.content_plain

    def test_name_50_chars_inclusive(self):
        """名称恰好 50 字 → 接受。"""
        name = "测" * 50
        tid = mk(name=name)
        assert tid > 0
        assert repo.get_task(tid).name == name

    def test_whitespace_only_name_rejected(self):
        """纯空白名称（strip 后为空）→ ValidationError。"""
        with pytest.raises(repo.ValidationError, match="任务名称"):
            repo.validate_task("   ", "执行人", "内容",
                               fmt(datetime.now() + timedelta(days=1)),
                               fmt(datetime.now() + timedelta(hours=1)))

    def test_html_in_assignee_stored_verbatim(self):
        """执行人含 HTML 标签 → 原样存储不崩溃（展示层按纯文本渲染，无执行面）。"""
        tid = mk(name="执行人HTML任务", assignee="<b>张</b>三")
        task = repo.get_task(tid)
        assert task.assignee == "<b>张</b>三"       # 原样存储
        assert html_to_plain(task.assignee) == "张三"  # 渲染时按纯文本
