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
        svc.task_due_batch.connect(lambda pairs: got.extend((t.id, hid) for t, hid in pairs))
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


class TestStormGuard:
    """防"提醒风暴"：单周期上限、最新优先、断线自愈、单条失败不拖垮整批。"""

    def test_tick_caps_at_max_per_tick(self, qtbot):
        import sqlite3  # noqa: F401（保持与其它用例一致的导入风格）
        from task_reminder.reminder_service import MAX_PER_TICK, ReminderService
        for i in range(MAX_PER_TICK + 5):
            mk(datetime.now() - timedelta(minutes=i + 1))
        svc = ReminderService()
        got = []
        svc.task_due_batch.connect(lambda p: got.extend(p))
        svc.tick()
        assert len(got) == MAX_PER_TICK           # 首批被截断
        svc.tick()
        assert len(got) == MAX_PER_TICK + 5       # 次周期补齐

    def test_due_limit_returns_newest_first(self):
        older = mk(datetime.now() - timedelta(hours=2))
        newer = mk(datetime.now() - timedelta(minutes=1))
        rows = repo.due_for_reminder(limit=1)
        assert len(rows) == 1
        assert rows[0].id == newer                # 最新的先弹
        assert {t.id for t in repo.due_for_reminder()} == {older, newer}

    def test_tick_self_heals_dead_connection(self, qtbot, monkeypatch):
        import sqlite3
        from task_reminder import reminder_service
        calls = {"n": 0}
        real = repo.due_for_reminder

        def flaky(now=None, limit=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise sqlite3.OperationalError("database connection lost")
            return real(limit=limit)

        monkeypatch.setattr(repo, "due_for_reminder", flaky)
        tid = mk(datetime.now() - timedelta(minutes=2))
        svc = reminder_service.ReminderService()
        got = []
        svc.task_due_batch.connect(lambda p: got.extend(p))
        svc.tick()
        assert calls["n"] >= 2                    # 失败后重连并重试
        assert len(got) == 1 and got[0][0].id == tid

    def test_single_mark_failure_skipped(self, qtbot, monkeypatch):
        import sqlite3
        from task_reminder.reminder_service import ReminderService
        t_bad = mk(datetime.now() - timedelta(minutes=3))
        t_ok = mk(datetime.now() - timedelta(minutes=2))
        real_mark = repo.mark_triggered

        def flaky_mark(tid):
            if tid == t_bad:
                raise sqlite3.OperationalError("database is locked")
            return real_mark(tid)

        monkeypatch.setattr(repo, "mark_triggered", flaky_mark)
        svc = ReminderService()
        got = []
        svc.task_due_batch.connect(lambda p: got.extend(p))
        svc.tick()
        assert [t.id for t, _ in got] == [t_ok]   # 失败条被跳过
        assert repo.get_task(t_bad).triggered == 0   # 留待下轮重试


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
