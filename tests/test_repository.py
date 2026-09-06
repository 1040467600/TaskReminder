"""repository 数据层单测：CRUD、校验、排序、搜索、分页、提醒、历史、保存搜索、统计。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from task_reminder import repository as repo
from task_reminder.models import TaskStatus, fmt


def mk(name="编写季度报告", assignee="张三", content="<b>重要</b>事项",
       deadline=None, reminder=None, status=TaskStatus.NOT_STARTED, notes=""):
    now = datetime.now()
    deadline = deadline or fmt(now + timedelta(days=1))
    reminder = reminder or fmt(now + timedelta(hours=2))
    return repo.add_task(name, assignee, content, deadline, reminder, status, notes)


# ---------------------------------------------------------------- 校验
class TestValidation:
    def test_name_too_short(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("", "张三", "x", "2026-09-10 10:00", "2026-09-09 10:00")

    def test_name_one_char_ok(self):
        """名称/执行人下限为 1 字符。"""
        tid = repo.add_task("A", "李", "x", "2026-09-10 10:00", "2026-09-09 10:00")
        assert repo.get_task(tid).name == "A"

    def test_name_too_long(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("长" * 51, "张三", "x", "2026-09-10 10:00", "2026-09-09 10:00")

    def test_assignee_length(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("合法名称", "", "x", "2026-09-10 10:00", "2026-09-09 10:00")

    def test_reminder_must_be_before_deadline(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("合法名称", "张三", "x", "2026-09-09 10:00", "2026-09-10 10:00")

    def test_equal_times_rejected(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("合法名称", "张三", "x", "2026-09-10 10:00", "2026-09-10 10:00")

    def test_content_limit(self, ):
        with pytest.raises(repo.ValidationError):
            repo.add_task("合法名称", "张三", "x" * 5001, "2026-09-10 10:00", "2026-09-09 10:00")

    def test_invalid_time(self):
        with pytest.raises(repo.ValidationError):
            repo.add_task("合法名称", "张三", "x", "not-a-time", "2026-09-09 10:00")


# ---------------------------------------------------------------- CRUD 与状态时间戳
class TestCrud:
    def test_add_and_get(self):
        tid = mk()
        t = repo.get_task(tid)
        assert t.id == tid
        assert t.name == "编写季度报告"
        assert t.status == TaskStatus.NOT_STARTED
        assert t.status_changed_at == ""  # 初始未开始不记时间戳
        assert t.content_plain() == "重要事项"

    def test_update_and_status_timestamp(self):
        tid = mk()
        t = repo.get_task(tid)
        repo.update_task(tid, name=t.name, assignee=t.assignee, content=t.content,
                         deadline=t.deadline, reminder_time=t.reminder_time,
                         status=TaskStatus.IN_PROGRESS, notes=t.notes)
        t = repo.get_task(tid)
        assert t.status == TaskStatus.IN_PROGRESS
        assert t.status_changed_at != ""

        first_ts = t.status_changed_at
        repo.update_task(tid, name=t.name, assignee=t.assignee, content=t.content,
                         deadline=t.deadline, reminder_time=t.reminder_time,
                         status=TaskStatus.IN_PROGRESS, notes="改备注")
        assert repo.get_task(tid).status_changed_at == first_ts  # 未变更状态不刷新

    def test_set_status_done_marks_triggered(self):
        tid = mk()
        repo.set_status(tid, TaskStatus.DONE)
        t = repo.get_task(tid)
        assert t.triggered == 1
        assert t.status_changed_at != ""

    def test_delete_task(self):
        tid = mk()
        repo.delete_task(tid)
        assert repo.get_task(tid) is None

    def test_delete_tasks_batch(self):
        ids = [mk(), mk(), mk()]
        assert repo.delete_tasks(ids[:2]) == 2
        assert repo.get_task(ids[0]) is None
        assert repo.get_task(ids[2]) is not None


# ---------------------------------------------------------------- 排序/分页/搜索
class TestQuery:
    def test_sort_by_deadline(self):
        a = mk(deadline="2026-09-20 10:00")
        b = mk(deadline="2026-09-10 10:00")
        rows, total = repo.list_tasks(sort_key="deadline", sort_dir="asc", page_size=10)
        assert [t.id for t in rows][:2] == [b, a] and total >= 2

    def test_sort_by_status_order(self):
        mk(status=TaskStatus.DONE)
        mk(status=TaskStatus.IN_PROGRESS)
        mk(status=TaskStatus.NOT_STARTED)
        rows, _ = repo.list_tasks(sort_key="status", sort_dir="asc", page_size=10)
        statuses = [t.status for t in rows[:3]]
        assert statuses == [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.DONE]

    def test_pagination(self):
        for i in range(5):
            mk(name=f"任务名称{i:02d}")
        rows, total = repo.list_tasks(page=1, page_size=2, sort_key="id", sort_dir="asc")
        assert len(rows) == 2 and total == 5
        rows2, _ = repo.list_tasks(page=3, page_size=2, sort_key="id", sort_dir="asc")
        assert len(rows2) == 1

    def test_search_assignee_exact(self):
        mk(assignee="张三")
        mk(assignee="李四", name="另一个任务")
        rows, total = repo.list_tasks(criteria={"assignee": "张三"})
        assert total == 1 and rows[0].assignee == "张三"

    def test_search_keyword_in_content_and_name(self):
        mk(name="数据库迁移任务", content="升级 <i>PostgreSQL</i>")
        mk(name="前端重构任务", content="改造报表页面")
        rows, total = repo.list_tasks(criteria={"keyword": "数据库"})
        assert total == 1
        rows, total = repo.list_tasks(criteria={"keyword": "报表"})
        assert total == 1

    def test_search_deadline_range(self):
        mk(deadline="2026-09-10 10:00")
        mk(deadline="2026-09-25 10:00")
        rows, total = repo.list_tasks(criteria={"deadline_from": "2026-09-20 00:00",
                                                "deadline_to": "2026-09-30 23:59"})
        assert total == 1 and rows[0].deadline == "2026-09-25 10:00"

    def test_search_created_range(self):
        tid = mk()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows, total = repo.list_tasks(criteria={"created_from": now})
        assert total >= 1
        rows, total = repo.list_tasks(criteria={"created_from": "2030-01-01 00:00"})
        assert total == 0

    def test_search_status_multi(self):
        mk(status=TaskStatus.IN_PROGRESS)
        mk(status=TaskStatus.DONE)
        rows, total = repo.list_tasks(criteria={"statuses": [TaskStatus.IN_PROGRESS,
                                                             TaskStatus.DONE]})
        assert total == 2


# ---------------------------------------------------------------- 提醒
class TestReminder:
    def test_due_for_reminder(self):
        past = fmt(datetime.now() - timedelta(minutes=10))
        mk(reminder=past)                                   # 应触发
        mk(reminder=fmt(datetime.now() + timedelta(hours=1)))  # 未到
        mk(status=TaskStatus.DONE, reminder=past)           # 已完成
        due = repo.due_for_reminder()
        assert len(due) == 1

    def test_mark_triggered_and_history(self):
        tid = mk()
        hid = repo.mark_triggered(tid)
        assert hid is not None
        assert repo.get_task(tid).triggered == 1
        logs, total = repo.list_history()
        assert total == 1
        assert logs[0].response_text() == "未响应"

    def test_history_response(self):
        tid = mk()
        hid = repo.mark_triggered(tid)
        repo.set_history_response(hid, "snooze")
        logs, _ = repo.list_history()
        assert logs[0].response == "snooze"
        assert logs[0].response_text() == "稍后提醒"
        assert logs[0].responded_at != ""

    def test_reset_triggered_for_new_day(self):
        yesterday = fmt(datetime.now() - timedelta(days=1))
        tid = mk(reminder=yesterday)
        repo.mark_triggered(tid)
        assert repo.get_task(tid).triggered == 1
        n = repo.reset_triggered_for_new_day()
        assert n == 1
        assert repo.get_task(tid).triggered == 0
        # 已完成的不重置
        tid2 = mk(reminder=yesterday, status=TaskStatus.DONE)
        repo.mark_triggered(tid2)
        repo.reset_triggered_for_new_day()
        assert repo.get_task(tid2).triggered == 1


# ---------------------------------------------------------------- 保存搜索 / 统计 / 冲突
class TestMisc:
    def test_saved_searches(self):
        repo.save_search("本周截止", {"deadline_from": "2026-09-08 00:00"})
        repo.save_search("本周截止", {"deadline_from": "2026-09-09 00:00"})  # 覆盖
        items = repo.list_searches()
        assert len(items) == 1 and items[0]["criteria"]["deadline_from"] == "2026-09-09 00:00"
        repo.save_search("我的任务", {"assignee": "张三"})
        repo.delete_search(items[0]["id"])
        assert len(repo.list_searches()) == 1

    def test_stats_and_upcoming(self):
        mk(status=TaskStatus.IN_PROGRESS)
        done = mk(status=TaskStatus.DONE)
        mk(deadline=fmt(datetime.now() - timedelta(days=1)),
           reminder=fmt(datetime.now() - timedelta(days=2)))  # 已过期
        s = repo.stats()
        assert s["total"] == 3
        assert s["by_status"][TaskStatus.DONE] == 1
        assert s["overdue"] == 1
        assert len(repo.upcoming_reminders()) >= 0
        assert len(repo.overdue_tasks()) == 1

    def test_find_duplicate(self):
        dl = "2026-09-10 10:00"
        mk(name="重复检测任务", deadline=dl)
        dup = repo.find_duplicate("重复检测任务", "张三", dl)
        assert dup is not None
        assert repo.find_duplicate("重复检测任务", "张三", "2026-09-11 10:00") is None

    def test_all_tasks_export_order(self):
        a = mk(deadline="2026-09-20 10:00")
        b = mk(deadline="2026-09-10 10:00")
        rows = repo.all_tasks(sort_key="deadline", sort_dir="asc")
        ids = [t.id for t in rows]
        assert ids.index(b) < ids.index(a)

    def test_clear_history(self):
        tid = mk()
        repo.mark_triggered(tid)
        assert repo.clear_history() >= 1
        assert repo.list_history()[1] == 0
