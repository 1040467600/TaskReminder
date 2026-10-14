"""第三轮新增测试：models / notifier / app_config / db / backup / repository 空白覆盖。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from task_reminder import app_config, backup, db, repository as repo
from task_reminder.models import (
    ReminderLog, Task, TaskStatus, fmt, html_to_plain, parse, plain_len,
)
from task_reminder.repository import ValidationError


# ======================================================================
# models.py
# ======================================================================
class TestHtmlToPlain:
    def test_empty_and_plain(self):
        assert html_to_plain("") == ""
        assert html_to_plain("纯文本没有标签") == "纯文本没有标签"

    def test_strip_tags(self):
        assert html_to_plain("<p>你好<b>世界</b></p>") == "你好世界"

    def test_br_and_block_to_newline(self):
        result = html_to_plain("a<br>b</p>c</div>d</li>e")
        assert "\n" in result
        assert result.replace("\n", "") == "abcde"

    def test_script_style_removed(self):
        html = "<script>alert(1)</script>正文<style>body{}</style>可见"
        assert "alert" not in html_to_plain(html)
        assert "可见" in html_to_plain(html)

    def test_entities_decoded(self):
        assert html_to_plain("a&nbsp;b&lt;&gt;&amp;&quot;c") == 'a b<>&"c'

    def test_unknown_entity_removed(self):
        assert html_to_plain("a&foobar;b") == "ab"

    def test_plain_len(self):
        assert plain_len("") == 0
        assert plain_len("<p>123</p>") == 3


class TestParseTime:
    def test_empty_returns_none(self):
        assert parse("") is None
        assert parse(None) is None if False else parse("") is None

    def test_standard_format(self):
        assert parse("2026-09-10 10:30").strftime("%Y-%m-%d %H:%M") == "2026-09-10 10:30"

    def test_t_separator(self):
        assert parse("2026-09-10T10:30") is not None

    def test_with_seconds(self):
        assert parse("2026-09-10 10:30:45") is not None

    def test_date_only(self):
        assert parse("2026-09-10") is not None

    def test_invalid_returns_none(self):
        assert parse("not-a-date") is None
        assert parse("明天下午") is None


class TestTaskMethods:
    def test_plain_text_prefers_content_plain(self):
        t = Task(content="<p>富文本</p>", content_plain="已落库纯文本")
        assert t.plain_text() == "已落库纯文本"

    def test_plain_text_fallback_to_html(self):
        t = Task(content="<p>富文本</p>", content_plain="")
        assert t.plain_text() == "富文本"

    def test_summary_uses_name(self):
        t = Task(name="季度报告")
        assert t.summary() == "季度报告"

    def test_summary_falls_back_to_content(self):
        t = Task(name="", content="<p>内容摘要</p>", content_plain="内容摘要")
        assert t.summary() == "内容摘要"

    def test_summary_truncates_long_name(self):
        t = Task(name="A" * 100)
        assert len(t.summary()) == 40 + 1  # 40 + ellipsis
        assert t.summary().endswith("…")

    def test_is_overdue_pending_with_past_deadline(self):
        t = Task(deadline=fmt(datetime.now() - timedelta(days=1)),
                 status=TaskStatus.NOT_STARTED)
        assert t.is_overdue() is True

    def test_is_overdone_task_not_overdue(self):
        t = Task(deadline=fmt(datetime.now() - timedelta(days=1)),
                 status=TaskStatus.DONE)
        assert t.is_overdue() is False

    def test_not_overdue_with_future_deadline(self):
        t = Task(deadline=fmt(datetime.now() + timedelta(days=1)))
        assert t.is_overdue() is False

    def test_not_overdue_with_empty_deadline(self):
        t = Task(deadline="")
        assert t.is_overdue() is False


class TestReminderLogResponseText:
    def test_known_responses(self):
        assert ReminderLog(response="").response_text() == "未响应"
        assert ReminderLog(response="snooze").response_text() == "稍后提醒"
        assert ReminderLog(response="done").response_text() == "标记完成"
        assert ReminderLog(response="close").response_text() == "关闭"

    def test_unknown_response_passthrough(self):
        assert ReminderLog(response="custom").response_text() == "custom"


# ======================================================================
# notifier.py
# ======================================================================
class TestRemainingText:
    def test_empty_or_invalid_deadline(self):
        from task_reminder.notifier import remaining_text
        assert remaining_text("") == ""
        assert remaining_text("garbage") == ""

    def test_future_deadline_shows_remaining(self):
        from task_reminder.notifier import remaining_text
        future = fmt(datetime.now() + timedelta(hours=2))
        assert "剩余" in remaining_text(future)

    def test_past_deadline_shows_overdue(self):
        from task_reminder.notifier import remaining_text
        past = fmt(datetime.now() - timedelta(days=3))
        text = remaining_text(past)
        assert "已过期" in text
        assert "3 天" in text


class TestNotifierQueue:
    def test_pending_count_empty(self, qtbot):
        from task_reminder.notifier import Notifier
        n = Notifier()
        assert n.pending_count() == 0

    def test_pending_count_with_queue(self, qtbot):
        from task_reminder.notifier import Notifier
        from task_reminder.models import Task
        n = Notifier()
        n.notify_batch([(Task(name="t1"), 1), (Task(name="t2"), 2)])
        assert n.pending_count() == 2

    def test_notify_batch_empty_noop(self, qtbot):
        from task_reminder.notifier import Notifier
        n = Notifier()
        before = n.pending_count()
        n.notify_batch([])
        assert n.pending_count() == before


class TestSnoozeLogic:
    def test_snooze_sets_future_reminder_and_resets_triggered(self, qtbot):
        """ReminderDialog._snooze：提醒时间顺延、triggered 重置为 0。"""
        now = datetime.now()
        tid = repo.add_task("打盹测试", "张三", "", fmt(now + timedelta(days=1)),
                            fmt(now + timedelta(hours=1)))
        repo.mark_triggered(tid)
        assert repo.get_task(tid).triggered == 1

        from task_reminder.notifier import ReminderDialog
        from task_reminder.models import parse
        dlg = ReminderDialog(repo.get_task(tid), 1)
        dlg._snooze(10)
        t = repo.get_task(tid)
        assert t.triggered == 0
        new_rt = parse(t.reminder_time)
        assert new_rt is not None
        # 至少比原来晚 8 分钟（留余量）
        assert new_rt >= now + timedelta(minutes=8)


# ======================================================================
# app_config.py
# ======================================================================
class TestAppConfig:
    def test_get_missing_returns_default(self):
        # 未设置的 key 走 DEFAULTS
        assert app_config.get("theme") in ("light", "dark")
        assert app_config.get("font_size") == 13
        assert app_config.get("poll_interval") == 5
        assert app_config.get("sound_enabled") is True
        assert app_config.get("page_size") == 200

    def test_get_with_fallback(self):
        assert app_config.get("no_such_key", "fallback") == "fallback"
        assert app_config.get("no_such_key", 42) == 42

    def test_set_and_get_roundtrip_types(self):
        app_config.set("int_val", 7)
        assert app_config.get("int_val") == 7
        app_config.set("bool_val", False)
        assert app_config.get("bool_val") is False
        app_config.set("list_val", [1, "a", True])
        assert app_config.get("list_val") == [1, "a", True]
        app_config.set("dict_val", {"k": "v", "n": 3})
        assert app_config.get("dict_val") == {"k": "v", "n": 3}

    def test_set_overwrites(self):
        app_config.set("theme", "dark")
        app_config.set("theme", "light")
        assert app_config.get("theme") == "light"

    def test_assets_dir_contains_assets(self):
        d = app_config.assets_dir()
        assert (d / "chime.wav").exists()

    def test_assets_dir_bundled_meipass(self, tmp_path, monkeypatch):
        fake = tmp_path / "assets"
        fake.mkdir()
        (fake / "chime.wav").write_bytes(b"x")
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        # 重新导入以生效
        import importlib
        importlib.reload(app_config)
        assert app_config.assets_dir() == fake
        # 清理 _MEIPASS 以免影响后续
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        importlib.reload(app_config)

    def test_default_sound_points_to_chime(self):
        p = Path(app_config.default_sound())
        assert p.name == "chime.wav"
        assert p.exists()

    def test_built_in_sounds_three_existing(self):
        sounds = app_config.built_in_sounds()
        assert len(sounds) == 3
        names = [n for n, _ in sounds]
        assert "清脆铃声" in names and "叮咚提示" in names and "紧急警报" in names
        for _, path in sounds:
            assert Path(path).exists()


# ======================================================================
# db.py
# ======================================================================
class TestDb:
    def test_busy_timeout_set(self):
        val = db.get_conn().execute("PRAGMA busy_timeout").fetchone()[0]
        assert val >= 3000

    def test_close_then_get_conn_reinits(self):
        db.close()
        # get_conn 应自动重建连接
        c = db.get_conn()
        assert c is not None
        # 仍可执行查询
        assert c.execute("SELECT 1").fetchone()[0] == 1

    def test_db_path_matches_init(self, tmp_path):
        p = str(tmp_path / "x.db")
        db.init(p)
        assert db.db_path() == p

    def test_foreign_keys_enabled(self):
        val = db.get_conn().execute("PRAGMA foreign_keys").fetchone()[0]
        assert val == 1


# ======================================================================
# backup.py
# ======================================================================
class TestBackupEdgeCases:
    def test_import_invalid_format_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"format": "wrong", "tasks": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            backup.import_json(str(bad))

    def test_export_creates_parent_dir(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "backup.json"
        n = backup.export_json(str(deep))
        assert n >= 0
        assert deep.exists()

    def test_history_round_trip(self, tmp_path):
        tid = repo.add_task("历史备份测试", "张三", "",
                            fmt(datetime.now() + timedelta(days=1)),
                            fmt(datetime.now() + timedelta(hours=1)))
        hid = repo.mark_triggered(tid)
        repo.set_history_response(hid, "done")

        path = str(tmp_path / "h.json")
        n_tasks = backup.export_json(path)
        assert n_tasks >= 1

        # 清库后恢复
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        # 清历史
        with db.get_conn() as c:
            c.execute("DELETE FROM reminder_history")
        nt, nh = backup.import_json(path)
        assert nt >= 1
        assert nh >= 1
        # 响应字段被恢复
        row = db.get_conn().execute(
            "SELECT response FROM reminder_history WHERE id=?", (hid,)
        ).fetchone()
        assert row["response"] == "done"

    def test_import_upsert_existing_task(self, tmp_path):
        """同 id 任务导入为更新而非重复。"""
        tid = repo.add_task("Upsert测试", "原执行人", "",
                            fmt(datetime.now() + timedelta(days=1)),
                            fmt(datetime.now() + timedelta(hours=1)))
        path = str(tmp_path / "u.json")
        backup.export_json(path)

        # 改本地同名任务内容
        repo.update_task(tid, name="Upsert测试", assignee="原执行人",
                         content="原内容", deadline=fmt(datetime.now() + timedelta(days=1)),
                         reminder_time=fmt(datetime.now() + timedelta(hours=1)),
                         status=TaskStatus.NOT_STARTED, notes="")

        # 再次导入应更新而非新增
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # 修改备份中任务内容为"新内容"
        for t in data["tasks"]:
            if t["id"] == tid:
                t["content"] = "新内容"
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        before = len(repo.all_tasks())
        nt, _ = backup.import_json(path)
        assert len(repo.all_tasks()) == before
        assert repo.get_task(tid).plain_text() == "新内容"


# ======================================================================
# repository.py 补充
# ======================================================================
class TestRepositoryAdditional:
    def test_delete_history_row_returns_false_for_nonexistent(self):
        assert repo.delete_history_row(999999) is False

    def test_delete_history_row_returns_true_for_existing(self):
        tid = repo.add_task("历史行删除", "张三", "",
                            fmt(datetime.now() + timedelta(days=1)),
                            fmt(datetime.now() + timedelta(hours=1)))
        hid = repo.mark_triggered(tid)
        assert repo.delete_history_row(hid) is True

    def test_stats_breakdown(self):
        # 清库
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        dl = fmt(datetime.now() + timedelta(days=1))
        rm = fmt(datetime.now() + timedelta(hours=1))
        repo.add_task("未开始任务", "A", "", dl, rm, TaskStatus.NOT_STARTED)
        repo.add_task("进行中任务", "B", "", dl, rm, TaskStatus.IN_PROGRESS)
        repo.add_task("已完成任务", "C", "", dl, rm, TaskStatus.DONE)

        stats = repo.stats()
        assert stats["total"] == 3
        assert stats["by_status"][TaskStatus.NOT_STARTED] == 1
        assert stats["by_status"][TaskStatus.IN_PROGRESS] == 1
        assert stats["by_status"][TaskStatus.DONE] == 1
        assert stats["overdue"] == 0  # 未来截止不过期

    def test_stats_overdue_count(self):
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        past_dl = fmt(datetime.now() - timedelta(days=1))
        past_rm = fmt(datetime.now() - timedelta(days=2))
        repo.add_task("过期未完成", "A", "", past_dl, past_rm, TaskStatus.NOT_STARTED)
        repo.add_task("过期已完成", "B", "", past_dl, past_rm, TaskStatus.DONE)
        stats = repo.stats()
        assert stats["overdue"] == 1  # 已完成不计入

    def test_list_history_date_range_filter(self):
        tid = repo.add_task("历史范围", "张三", "",
                            fmt(datetime.now() + timedelta(days=1)),
                            fmt(datetime.now() + timedelta(hours=1)))
        hid = repo.mark_triggered(tid)
        today = datetime.now().strftime("%Y-%m-%d")
        today_end = today + " 23:59"
        # 当天范围应能查到
        _, total = repo.list_history(1, 50, today, today_end)
        assert total >= 1
        # 明天范围应查不到（历史触发在今天）
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        _, total2 = repo.list_history(1, 50, tomorrow, tomorrow + " 23:59")
        assert total2 == 0

    def test_find_duplicate_matches_name_assignee_deadline(self):
        dl = fmt(datetime.now() + timedelta(days=1))
        rm = fmt(datetime.now() + timedelta(hours=1))
        tid = repo.add_task("重复检测", "张三", "", dl, rm)
        dup = repo.find_duplicate("重复检测", "张三", dl)
        assert dup is not None and dup.id == tid
        # 执行人不同 → 不重复
        assert repo.find_duplicate("重复检测", "李四", dl) is None
        # 截止不同 → 不重复
        other_dl = fmt(datetime.now() + timedelta(days=2))
        assert repo.find_duplicate("重复检测", "张三", other_dl) is None

    def test_validate_task_name_length_boundaries(self):
        dl = fmt(datetime.now() + timedelta(days=1))
        rm = fmt(datetime.now() + timedelta(hours=1))
        # 1 字符合法
        repo.validate_task("x", "张三", "", dl, rm)
        # 0 字符非法
        with pytest.raises(ValidationError):
            repo.validate_task("", "张三", "", dl, rm)
        # 50 字符合法，51 非法
        repo.validate_task("A" * 50, "张三", "", dl, rm)
        with pytest.raises(ValidationError):
            repo.validate_task("A" * 51, "张三", "", dl, rm)

    def test_overdue_tasks_excludes_empty_deadline(self):
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        # 无截止时间任务不进入 overdue
        repo.add_task("无截止", "A", "", "", "")
        assert len(repo.overdue_tasks()) == 0
