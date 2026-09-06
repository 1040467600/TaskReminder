"""提醒服务与通知逻辑单测（offscreen 运行）。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from task_reminder import repository as repo
from task_reminder.models import TaskStatus, fmt


def mk(reminder, status=TaskStatus.NOT_STARTED, name="合法的任务名称"):
    now = datetime.now()
    return repo.add_task(name, "张三", "内容", fmt(now + timedelta(days=1)), fmt(reminder), status)


class TestReminderService:
    def test_tick_emits_due(self, qtbot):
        from task_reminder.reminder_service import ReminderService
        past = datetime.now() - timedelta(minutes=5)
        future = datetime.now() + timedelta(hours=1)
        tid1 = mk(past)
        mk(future)
        svc = ReminderService()
        got = []
        svc.task_due.connect(lambda t, hid: got.append((t.id, hid)))
        svc.tick()
        assert len(got) == 1                       # 未到期的不触发
        assert got[0][0] == tid1
        assert got[0][1] > 0                       # 已写入提醒历史
        assert repo.get_task(tid1).triggered == 1  # 标记已触发
        assert len(got) == 1                       # 未到期的不触发

    def test_interval_bounds(self, qtbot):
        from task_reminder import app_config
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", 120)
        svc = ReminderService()
        svc.apply_interval()
        assert svc._timer.interval() == 60000
        app_config.set("poll_interval", 0)
        svc.apply_interval()
        assert svc._timer.interval() == 1000
        app_config.set("poll_interval", 5)


class TestNotifierLogic:
    def test_queue_and_dialog(self, qtbot):
        from task_reminder.notifier import Notifier, ReminderDialog
        past = datetime.now() - timedelta(minutes=1)
        tid = mk(past)
        hid = repo.mark_triggered(tid)
        n = Notifier()
        counts = []
        n.queue_changed.connect(counts.append)
        task = repo.get_task(tid)
        n.notify(task, hid)
        n.notify(task, hid)
        assert n.pending_count() == 2
        n.pump()
        assert n._dialog is not None
        assert n.pending_count() == 2              # 队列 1 + 弹窗 1
        dlg = n._dialog
        dlg._respond("done")
        assert dlg.response == "done"
        # 修复 #2：关闭后队列中的下一条提醒应立即自动弹出，而不是等下一轮轮询
        assert n._dialog is not None and n._dialog is not dlg
        n._dialog._respond("done")
        assert n._dialog is None
        assert n.pending_count() == 0
        assert repo.get_task(tid).status == TaskStatus.DONE
        log = repo.list_history()[0][0]
        assert log.response == "done"

    def test_snooze_defers(self, qtbot):
        from task_reminder.notifier import ReminderDialog
        past = datetime.now() - timedelta(minutes=1)
        tid = mk(past)
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        dlg = ReminderDialog(task, hid)
        dlg._respond("snooze")
        t = repo.get_task(tid)
        assert t.triggered == 0                    # 允许再次触发
        from task_reminder.models import parse
        new_rt = parse(t.reminder_time)
        assert new_rt > datetime.now()             # 已顺延
        log = repo.list_history()[0][0]
        assert log.response == "snooze"


class TestSoundFallback:
    def test_play_disabled(self):
        from task_reminder.sound import SoundPlayer
        sp = SoundPlayer()
        assert sp.play(enabled=False) is False

    def test_play_missing_file_fallback(self):
        from task_reminder.sound import SoundPlayer
        sp = SoundPlayer()
        result = sp.play(path="Z:/no/such.wav", enabled=True)
        assert result is True                      # winsound 回退成功
