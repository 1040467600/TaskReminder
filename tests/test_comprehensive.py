"""综合测试：覆盖核心模块的正常流程、边界条件、异常场景。

测试类型：
- 单元测试：models / db / app_config / notifier / reminder_service
- 集成测试：backup / excel_io / search_bar / task_dialog
- 功能测试：dashboard_page / widgets / tasks_page

每个测试类覆盖一个核心模块，每个方法包含明确的测试目的、输入数据、预期输出和验证方法。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PyQt6.QtCore import QDate, QDateTime, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from task_reminder import app_config, backup, db, repository as repo
from task_reminder.models import (CONTENT_MAX, NAME_MAX, NAME_MIN, NOTES_MAX,
                                  ReminderLog, Task, TaskStatus, fmt, html_to_plain,
                                  parse, plain_len)


def mk(**kw):
    """创建一条测试任务，返回 task_id。"""
    now = datetime.now()
    d = dict(name="综合测试任务", assignee="测试员", content="<b>内容</b>",
             deadline=fmt(now + timedelta(days=1)), reminder=fmt(now + timedelta(hours=1)),
             status=TaskStatus.NOT_STARTED, notes="")
    d.update(kw)
    return repo.add_task(d["name"], d["assignee"], d["content"], d["deadline"], d["reminder"],
                         d["status"], d["notes"])


# ===========================================================================
# 单元测试：models.py — 纯函数与数据类
# ===========================================================================
class TestHtmlToPlain:
    """html_to_plain：富文本 → 纯文本转换，覆盖空、纯文本、复杂 HTML、实体。"""

    def test_empty_string(self):
        """空字符串输入 → 空字符串输出。"""
        assert html_to_plain("") == ""

    def test_none_input(self):
        """None 输入 → 空字符串输出。"""
        assert html_to_plain(None) == ""

    def test_plain_text_fast_path(self):
        """不含 < 和 & 的纯文本 → 原样返回（快速路径）。"""
        assert html_to_plain("普通文本内容") == "普通文本内容"

    def test_simple_bold(self):
        """简单加粗标签 → 去标签保留内容。"""
        assert html_to_plain("<b>加粗</b>") == "加粗"

    def test_nested_tags(self):
        """嵌套标签 → 全部去标签保留文字。"""
        result = html_to_plain("<div><p>段落<b>加粗</b>普通</p></div>")
        assert "段落" in result and "加粗" in result and "普通" in result

    def test_br_becomes_newline(self):
        """<br> 标签 → 转为换行。"""
        result = html_to_plain("第一行<br>第二行")
        assert "第一行\n第二行" == result

    def test_html_entities_decoded(self):
        """HTML 实体 → 解码为原始字符。"""
        assert html_to_plain("&lt;tag&gt;") == "<tag>"
        assert html_to_plain("a&nbsp;b") == "a b"
        assert html_to_plain("&quot;引号&quot;") == '"引号"'

    def test_style_script_removed(self):
        """<style>/<script> 标签内容被移除。"""
        result = html_to_plain("<style>body{color:red}</style>正文")
        assert "color" not in result and "正文" in result

    def test_strips_leading_trailing_whitespace(self):
        """前后空白被 strip。"""
        assert html_to_plain("  <b>内容</b>  ") == "内容"


class TestPlainLen:
    """plain_len：富文本纯文本长度计算。"""

    def test_empty(self):
        assert plain_len("") == 0

    def test_plain_text(self):
        assert plain_len("12345") == 5

    def test_html(self):
        """HTML 长度按纯文本计算（标签不计入）。"""
        assert plain_len("<b>12345</b>") == 5

    def test_at_content_limit(self):
        """刚好 5000 字 → 不超限。"""
        text = "字" * CONTENT_MAX
        assert plain_len(text) == CONTENT_MAX

    def test_over_content_limit(self):
        """超过 5000 字 → 返回实际长度。"""
        text = "字" * (CONTENT_MAX + 1)
        assert plain_len(text) == CONTENT_MAX + 1


class TestParse:
    """parse：时间字符串解析，覆盖多种格式。"""

    def test_empty(self):
        """空字符串 → None。"""
        assert parse("") is None
        assert parse(None) is None

    def test_standard_format(self):
        """标准格式 'YYYY-MM-DD HH:MM' → 正确解析。"""
        dt = parse("2026-09-10 14:30")
        assert dt is not None
        assert dt.year == 2026 and dt.month == 9 and dt.day == 10
        assert dt.hour == 14 and dt.minute == 30

    def test_t_separator(self):
        """T 分隔符 → 兼容解析。"""
        dt = parse("2026-09-10T14:30")
        assert dt is not None and dt.hour == 14

    def test_with_seconds(self):
        """含秒格式 → 兼容解析。"""
        dt = parse("2026-09-10 14:30:45")
        assert dt is not None and dt.second == 45

    def test_date_only(self):
        """仅日期格式 → 兼容解析。"""
        dt = parse("2026-09-10")
        assert dt is not None and dt.hour == 0 and dt.minute == 0

    def test_invalid(self):
        """无效字符串 → None。"""
        assert parse("not-a-date") is None
        assert parse("2026/09/10") is None  # 斜杠不兼容


class TestTaskDataclass:
    """Task 数据类方法测试。"""

    def test_plain_text_prefers_content_plain(self):
        """plain_text 优先使用落库的 content_plain 列。"""
        t = Task(name="test", content="<b>富文本</b>", content_plain="纯文本冗余")
        assert t.plain_text() == "纯文本冗余"

    def test_plain_text_fallback_to_html(self):
        """content_plain 为空时从富文本现算。"""
        t = Task(name="test", content="<b>富文本</b>", content_plain="")
        assert t.plain_text() == "富文本"

    def test_plain_text_empty_content(self):
        """内容和冗余列都为空 → 空字符串。"""
        t = Task(name="test", content="", content_plain="")
        assert t.plain_text() == ""

    def test_summary_uses_name(self):
        """summary 优先使用任务名称。"""
        t = Task(name="任务名称", content="内容")
        assert t.summary() == "任务名称"

    def test_summary_falls_back_to_content(self):
        """名称为空时使用内容摘要。"""
        t = Task(name="", content="<b>这是内容</b>")
        assert "这是内容" in t.summary()

    def test_summary_truncates_with_ellipsis(self):
        """超长名称被截断并加省略号。"""
        long_name = "A" * 100
        t = Task(name=long_name)
        s = t.summary(limit=10)
        assert s.endswith("…")
        assert len(s) == 11  # 10 字 + 省略号

    def test_summary_no_truncation_under_limit(self):
        """短名称不加省略号。"""
        t = Task(name="短名称")
        assert t.summary() == "短名称"
        assert "…" not in t.summary()

    def test_is_overdue_true(self):
        """截止时间在过去且未完成 → 过期。"""
        t = Task(deadline="2020-01-01 00:00", status=TaskStatus.NOT_STARTED)
        assert t.is_overdue() is True

    def test_is_overdue_false_future(self):
        """截止时间在未来 → 未过期。"""
        future = fmt(datetime.now() + timedelta(days=10))
        t = Task(deadline=future, status=TaskStatus.NOT_STARTED)
        assert t.is_overdue() is False

    def test_is_overdue_false_done(self):
        """已完成的任务即使过期也不算过期。"""
        t = Task(deadline="2020-01-01 00:00", status=TaskStatus.DONE)
        assert t.is_overdue() is False

    def test_is_overdue_empty_deadline(self):
        """截止时间为空 → 未过期。"""
        t = Task(deadline="", status=TaskStatus.NOT_STARTED)
        assert t.is_overdue() is False

    def test_from_row(self):
        """from_row 从 sqlite3.Row 构造 Task（先建数据，避免空转）。"""
        tid = mk(name="行构造测试")
        conn = db.get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        assert row is not None  # 前置条件必须成立，否则测试无意义
        t = Task.from_row(row)
        assert t.id == tid
        assert t.name == "行构造测试"

    def test_from_row_empty_keys(self):
        """from_row 处理无 keys 属性的对象。"""
        t = Task.from_row({"id": 1, "name": "test"})
        assert t.id == 1 and t.name == "test"


class TestReminderLog:
    """ReminderLog 数据类测试。"""

    def test_response_text_known(self):
        """已知响应码 → 中文文本。"""
        assert ReminderLog(response="").response_text() == "未响应"
        assert ReminderLog(response="snooze").response_text() == "稍后提醒"
        assert ReminderLog(response="done").response_text() == "标记完成"
        assert ReminderLog(response="close").response_text() == "关闭"

    def test_response_text_unknown(self):
        """未知响应码 → 原样返回。"""
        assert ReminderLog(response="custom").response_text() == "custom"

    def test_from_row(self):
        """from_row 从 dict 构造。"""
        log = ReminderLog.from_row({"id": 1, "task_id": 2, "response": "done"})
        assert log.id == 1 and log.task_id == 2 and log.response == "done"


# ===========================================================================
# 单元测试：db.py — 数据库连接、schema、迁移
# ===========================================================================
class TestDb:
    """数据库层：迁移、事务、连接管理。"""

    def test_default_db_path(self):
        """默认数据库路径在 APPDATA/TaskReminder/ 下。"""
        path = db.default_db_path()
        assert "TaskReminder" in path
        assert path.endswith("tasks.db")

    def test_init_creates_schema(self, tmp_path):
        """init 后表和索引都存在。"""
        path = str(tmp_path / "test_schema.db")
        conn = db.init(path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "tasks" in tables
        assert "reminder_history" in tables
        assert "user_settings" in tables

    def test_init_idempotent(self, tmp_path):
        """重复调用 init 不报错：旧连接被关闭，新连接 schema 完整。"""
        path = str(tmp_path / "test_idem.db")
        conn1 = db.init(path)
        conn1.execute("INSERT INTO user_settings(key, value) VALUES(?, ?)",
                      ("idem_key", '"idem_val"'))
        conn1.commit()
        db.init(path)  # 再次初始化（关闭旧连接 + 重建）
        # 新连接可正常查询且 schema 完整
        conn = db.get_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert {"tasks", "reminder_history", "user_settings"} <= tables
        # 重新 init 走 ensure_schema（IF NOT EXISTS），旧数据不丢
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key=?", ("idem_key",)
        ).fetchone()
        assert row is not None and row["value"] == '"idem_val"'

    def test_transaction_commit(self, tmp_path):
        """transaction 正常提交。"""
        path = str(tmp_path / "test_tx.db")
        db.init(path)
        with db.transaction() as c:
            c.execute("INSERT INTO user_settings(key, value) VALUES(?, ?)", ("test_k", "test_v"))
        row = db.get_conn().execute(
            "SELECT value FROM user_settings WHERE key=?", ("test_k",)
        ).fetchone()
        assert row["value"] == "test_v"

    def test_transaction_rollback(self, tmp_path):
        """transaction 中抛异常 → 回滚。"""
        path = str(tmp_path / "test_rollback.db")
        db.init(path)
        with pytest.raises(RuntimeError):
            with db.transaction() as c:
                c.execute("INSERT INTO user_settings(key, value) VALUES(?, ?)", ("k1", "v1"))
                raise RuntimeError("故意失败")
        row = db.get_conn().execute(
            "SELECT value FROM user_settings WHERE key=?", ("k1",)
        ).fetchone()
        assert row is None

    def test_content_plain_backfill(self, tmp_path):
        """迁移：旧表无 content_plain 列时自动回填。"""
        path = str(tmp_path / "test_migrate.db")
        # 手动创建旧 schema（无 content_plain 列）
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                assignee TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                deadline TEXT NOT NULL DEFAULT '',
                reminder_time TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '未开始',
                notes TEXT NOT NULL DEFAULT '',
                triggered INTEGER NOT NULL DEFAULT 0,
                status_changed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );
        """)
        conn.execute(
            "INSERT INTO tasks(name, assignee, content, deadline, reminder_time)"
            " VALUES(?,?,?,?,?)",
            ("旧任务", "张三", "<b>旧内容</b>", "2026-09-10 10:00", "2026-09-09 09:00"),
        )
        conn.commit()
        conn.close()
        # init 应触发迁移：添加 content_plain 列并回填
        db.init(path)
        row = db.get_conn().execute("SELECT content_plain FROM tasks WHERE name='旧任务'").fetchone()
        assert row["content_plain"] == "旧内容"

    def test_close_resets_connection(self, tmp_path):
        """close 后 _conn 变 None，下次 get_conn 自动重建。"""
        path = str(tmp_path / "test_close.db")
        db.init(path)
        db.close()
        assert db._conn is None
        # get_conn 自动重建
        conn = db.get_conn()
        assert conn is not None


# ===========================================================================
# 单元测试：app_config.py — 配置持久化
# ===========================================================================
class TestAppConfig:
    """配置读写：类型序列化、默认值、覆盖。"""

    def test_get_default(self):
        """未设置过的 key → 返回 DEFAULTS 中的默认值。"""
        assert app_config.get("theme") == "light"
        assert app_config.get("font_size") == 13
        assert app_config.get("poll_interval") == 5

    def test_get_with_explicit_default(self):
        """未设置过的 key + 显式 default → 返回显式默认值。"""
        assert app_config.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get_string(self):
        """set 字符串 → get 回读一致。"""
        app_config.set("theme", "dark")
        assert app_config.get("theme") == "dark"

    def test_set_and_get_int(self):
        """set 整数 → get 回读为整数（JSON 序列化/反序列化）。"""
        app_config.set("font_size", 16)
        assert app_config.get("font_size") == 16
        assert isinstance(app_config.get("font_size"), int)

    def test_set_and_get_bool(self):
        """set 布尔值 → get 回读为布尔值。"""
        app_config.set("sound_enabled", False)
        assert app_config.get("sound_enabled") is False

    def test_set_and_get_list(self):
        """set 列表 → get 回读为列表。"""
        app_config.set("test_list", [1, 2, 3])
        assert app_config.get("test_list") == [1, 2, 3]

    def test_set_and_get_dict(self):
        """set 字典 → get 回读为字典。"""
        app_config.set("test_dict", {"a": 1, "b": "x"})
        assert app_config.get("test_dict") == {"a": 1, "b": "x"}

    def test_set_overwrites(self):
        """重复 set 同一 key → 覆盖旧值。"""
        app_config.set("theme", "dark")
        app_config.set("theme", "light")
        assert app_config.get("theme") == "light"

    def test_raw_value_non_json(self):
        """_raw 返回原始字符串（非 JSON 场景）。"""
        app_config.set("plain_key", "plain_value")
        raw = app_config._raw("plain_key")
        assert raw == "plain_value"

    def test_default_sound_path(self):
        """default_sound 返回路径含 chime.wav。"""
        path = app_config.default_sound()
        assert "chime.wav" in path

    def test_built_in_sounds(self):
        """built_in_sounds 返回 3 种内置音效。"""
        sounds = app_config.built_in_sounds()
        assert len(sounds) == 3
        for name, path in sounds:
            assert isinstance(name, str) and isinstance(path, str)


# ===========================================================================
# 单元测试：notifier.py — 提醒通知逻辑
# ===========================================================================
class TestRemainingText:
    """remaining_text：截止时间剩余/过期文本。"""

    def test_empty_deadline(self):
        """空截止时间 → 空字符串。"""
        from task_reminder.notifier import remaining_text
        assert remaining_text("") == ""

    def test_invalid_deadline(self):
        """无效截止时间 → 空字符串。"""
        from task_reminder.notifier import remaining_text
        assert remaining_text("not-a-date") == ""

    def test_future_deadline(self):
        """未来截止时间 → 剩余文本。"""
        from task_reminder.notifier import remaining_text
        future = fmt(datetime.now() + timedelta(days=2, hours=5))
        result = remaining_text(future)
        assert "剩余" in result
        assert "天" in result

    def test_past_deadline(self):
        """过去截止时间 → 已过期文本。"""
        from task_reminder.notifier import remaining_text
        past = fmt(datetime.now() - timedelta(days=1))
        result = remaining_text(past)
        assert "已过期" in result

    def test_near_future_shows_hours(self):
        """几小时后的截止 → 显示小时和分钟。"""
        from task_reminder.notifier import remaining_text
        future = fmt(datetime.now() + timedelta(hours=2, minutes=30))
        result = remaining_text(future)
        assert "小时" in result


class TestNotifierQueue:
    """Notifier 队列与弹窗管理。"""

    def test_notify_increments_queue(self, qtbot):
        """notify 入队 → pending_count 增加。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        n.notify(task, hid)
        assert n.pending_count() == 1
        n.notify(task, hid)
        assert n.pending_count() == 2

    def test_pump_shows_dialog(self, qtbot):
        """pump 弹出队首提醒弹窗。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        n.notify(task, hid)
        n.pump()
        assert n._dialog is not None
        assert n.pending_count() == 1  # 弹窗 1，队列 0

    def test_pump_empty_queue_noop(self, qtbot):
        """空队列 pump → 不弹窗。"""
        from task_reminder.notifier import Notifier
        n = Notifier()
        n.pump()
        assert n._dialog is None
        assert n.pending_count() == 0

    def test_pump_while_dialog_open_noop(self, qtbot):
        """已有弹窗时 pump → 不弹第二个。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        n.notify(task, hid)
        n.notify(task, hid)
        n.pump()
        first_dlg = n._dialog
        n.pump()  # 不应弹第二个
        assert n._dialog is first_dlg

    def test_queue_changed_signal(self, qtbot):
        """notify 触发 queue_changed 信号。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        counts = []
        n.queue_changed.connect(counts.append)
        n.notify(task, hid)
        assert len(counts) > 0
        assert counts[-1] == 1

    def test_responded_signal_on_done(self, qtbot):
        """弹窗点'标记完成' → responded 信号收到 'done'。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        responses = []
        n.responded.connect(responses.append)
        n.notify(task, hid)
        n.pump()
        n._dialog._respond("done")
        assert responses == ["done"]
        assert repo.get_task(tid).status == TaskStatus.DONE

    def test_responded_signal_on_close(self, qtbot):
        """弹窗点'关闭' → responded 信号收到 'close'，任务状态不变。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        responses = []
        n.responded.connect(responses.append)
        n.notify(task, hid)
        n.pump()
        n._dialog._respond("close")
        assert responses == ["close"]
        assert repo.get_task(tid).status != TaskStatus.DONE

    def test_snooze_5_minutes(self, qtbot):
        """稍后提醒 5 分钟 → reminder_time 顺延、triggered 重置。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        n.notify(task, hid)
        n.pump()
        n._dialog._respond("snooze", minutes=5)
        t = repo.get_task(tid)
        assert t.triggered == 0
        new_rt = parse(t.reminder_time)
        assert new_rt > datetime.now()

    def test_snooze_60_minutes(self, qtbot):
        """稍后提醒 60 分钟 → reminder_time 至少顺延 60 分钟。"""
        from task_reminder.notifier import Notifier
        tid = mk()
        hid = repo.mark_triggered(tid)
        task = repo.get_task(tid)
        n = Notifier()
        n.notify(task, hid)
        n.pump()
        n._dialog._respond("snooze", minutes=60)
        t = repo.get_task(tid)
        new_rt = parse(t.reminder_time)
        assert new_rt >= datetime.now() + timedelta(minutes=55)  # 允许几秒误差


# ===========================================================================
# 单元测试：reminder_service.py — 提醒调度
# ===========================================================================
class TestReminderService:
    """ReminderService：定时轮询、跨日重置、异常容错。"""

    def test_start_stop(self, qtbot):
        """start → 定时器运行；stop → 定时器停止。"""
        from task_reminder.reminder_service import ReminderService
        svc = ReminderService()
        svc.start()
        assert svc._timer.isActive()
        svc.stop()
        assert not svc._timer.isActive()

    def test_apply_interval_from_config(self, qtbot):
        """apply_interval 从配置读取间隔。"""
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", 10)
        svc = ReminderService()
        svc.apply_interval()
        assert svc._timer.interval() == 10000
        app_config.set("poll_interval", 5)

    def test_apply_interval_clamps_upper(self, qtbot):
        """间隔超过 60 秒 → 钳制为 60 秒。"""
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", 120)
        svc = ReminderService()
        svc.apply_interval()
        assert svc._timer.interval() == 60000
        app_config.set("poll_interval", 5)

    def test_apply_interval_clamps_lower(self, qtbot):
        """间隔低于 1 秒 → 钳制为 1 秒。"""
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", 0)
        svc = ReminderService()
        svc.apply_interval()
        assert svc._timer.interval() == 1000
        app_config.set("poll_interval", 5)

    def test_apply_interval_invalid_fallback(self, qtbot):
        """非数字间隔 → 回退 5 秒。"""
        from task_reminder.reminder_service import ReminderService
        app_config.set("poll_interval", "abc")
        svc = ReminderService()
        svc.apply_interval()
        assert svc._timer.interval() == 5000
        app_config.set("poll_interval", 5)

    def test_tick_emits_due_signal(self, qtbot):
        """tick 触发到期任务的 task_due 信号。"""
        from task_reminder.reminder_service import ReminderService
        past = datetime.now() - timedelta(minutes=5)
        tid = mk(reminder=fmt(past))
        svc = ReminderService()
        got = []
        svc.task_due.connect(lambda t, hid: got.append((t.id, hid)))
        svc.tick()
        assert len(got) == 1
        assert got[0][0] == tid
        assert repo.get_task(tid).triggered == 1

    def test_tick_no_due_no_emit(self, qtbot):
        """无到期任务 → tick 不发信号。"""
        from task_reminder.reminder_service import ReminderService
        future = fmt(datetime.now() + timedelta(hours=1))
        mk(reminder=future)
        svc = ReminderService()
        got = []
        svc.task_due.connect(lambda t, hid: got.append((t, hid)))
        svc.tick()
        assert len(got) == 0

    def test_maybe_reset_for_new_day(self, qtbot):
        """跨日重置：_last_reset_date 变化时调用 reset_triggered_for_new_day。"""
        from task_reminder.reminder_service import ReminderService
        yesterday = fmt(datetime.now() - timedelta(days=1))
        tid = mk(reminder=yesterday)
        repo.mark_triggered(tid)
        assert repo.get_task(tid).triggered == 1
        svc = ReminderService()
        svc._last_reset_date = "2020-01-01"  # 强制触发重置
        svc._maybe_reset_for_new_day()
        assert repo.get_task(tid).triggered == 0
        today = datetime.now().strftime("%Y-%m-%d")
        assert svc._last_reset_date == today

    def test_maybe_reset_same_day_skipped(self, qtbot):
        """同日不重复重置。"""
        from task_reminder.reminder_service import ReminderService
        today = datetime.now().strftime("%Y-%m-%d")
        svc = ReminderService()
        svc._last_reset_date = today
        # 不应崩溃
        svc._maybe_reset_for_new_day()
        assert svc._last_reset_date == today

    def test_tick_exception_swallowed(self, qtbot, monkeypatch):
        """tick 中 due_for_reminder 抛异常 → 不崩溃，静默返回。"""
        from task_reminder.reminder_service import ReminderService

        def boom():
            raise sqlite3.OperationalError("DB locked")
        monkeypatch.setattr(repo, "due_for_reminder", boom)
        svc = ReminderService()
        svc.tick()  # 不应抛异常


# ===========================================================================
# 集成测试：backup.py — 备份恢复
# ===========================================================================
class TestBackupAdvanced:
    """备份恢复高级场景：部分数据、字段缺失、历史独立恢复。"""

    def test_export_includes_history(self, tmp_path):
        """导出包含提醒历史记录。"""
        tid = mk()
        repo.mark_triggered(tid)
        path = str(tmp_path / "full.json")
        n = backup.export_json(path)
        assert n == 1
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert len(data["history"]) == 1
        assert data["format"] == "task_reminder_backup"
        assert data["version"] == backup.FORMAT_VERSION

    def test_import_only_tasks_no_history(self, tmp_path):
        """导入仅含任务无历史的备份 → 不崩溃。"""
        tid = mk()
        path = str(tmp_path / "tasks_only.json")
        backup.export_json(path)
        # 删掉 history 部分
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["history"] = []
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        repo.delete_task(tid)
        t, h = backup.import_json(path)
        assert t == 1 and h == 0

    def test_import_only_history_no_tasks(self, tmp_path):
        """导入仅含历史无任务的备份 → 不崩溃。"""
        tid = mk()
        hid = repo.mark_triggered(tid)
        path = str(tmp_path / "hist_only.json")
        backup.export_json(path)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["tasks"] = []
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        t, h = backup.import_json(path)
        assert t == 0 and h >= 1

    def test_import_upserts_existing_id(self, tmp_path):
        """导入同 id 任务 → 覆盖更新而非新建。"""
        tid = mk(name="原始名称")
        path = str(tmp_path / "upsert.json")
        backup.export_json(path)
        # 修改备份中的任务名称
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["tasks"][0]["name"] = "修改后名称"
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        t, h = backup.import_json(path)
        assert t == 1
        assert repo.get_task(tid).name == "修改后名称"

    def test_export_creates_parent_dir(self, tmp_path):
        """导出到不存在的子目录 → 自动创建。"""
        mk()
        path = str(tmp_path / "sub" / "dir" / "backup.json")
        n = backup.export_json(path)
        assert n == 1
        assert Path(path).exists()

    def test_export_empty_db(self, tmp_path):
        """空数据库导出 → 0 条任务，文件仍有效。"""
        path = str(tmp_path / "empty.json")
        n = backup.export_json(path)
        assert n == 0
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["tasks"] == []
        assert data["history"] == []

    def test_import_recomputes_content_plain(self, tmp_path):
        """导入时重算 content_plain（兼容旧备份无此列）。"""
        tid = mk(content="<b>富文本内容</b>")
        path = str(tmp_path / "old_backup.json")
        backup.export_json(path)
        # 模拟旧备份：删除 content_plain 字段
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        del data["tasks"][0]["content_plain"]
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        repo.delete_task(tid)
        backup.import_json(path)
        t = repo.get_task(tid)
        assert t.content_plain == "富文本内容"

    def test_import_invalid_json_raises(self, tmp_path):
        """非法 JSON 文件 → ValueError。"""
        p = tmp_path / "bad.json"
        p.write_text("not json at all", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            backup.import_json(str(p))


# ===========================================================================
# 集成测试：excel_io.py — 导入导出辅助函数
# ===========================================================================
class TestExcelHelpers:
    """Excel I/O 辅助函数与边界场景。"""

    def test_cell_time_datetime(self):
        """datetime 对象 → 格式化为字符串。"""
        from task_reminder.excel_io import _cell_time
        dt = datetime(2026, 9, 15, 8, 30)
        assert _cell_time(dt) == "2026-09-15 08:30"

    def test_cell_time_string_standard(self):
        """标准格式字符串 → 原样返回。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("2026-09-15 08:30") == "2026-09-15 08:30"

    def test_cell_time_with_seconds(self):
        """含秒格式 → 截断为分钟。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("2026-09-15 08:30:45") == "2026-09-15 08:30"

    def test_cell_time_t_separator(self):
        """T 分隔符 → 兼容。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("2026-09-15T08:30") == "2026-09-15 08:30"

    def test_cell_time_slash_separator(self):
        """斜杠分隔 → 兼容。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("2026/09/15 08:30") == "2026-09-15 08:30"

    def test_cell_time_date_only(self):
        """仅日期 → 补 00:00。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("2026-09-15") == "2026-09-15 00:00"

    def test_cell_time_none(self):
        """None → None。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time(None) is None

    def test_cell_time_empty(self):
        """空字符串 → None。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("") is None

    def test_cell_time_invalid(self):
        """无效字符串 → None。"""
        from task_reminder.excel_io import _cell_time
        assert _cell_time("not-a-date") is None

    def test_import_report_summary(self):
        """ImportReport.summary 包含各项统计。"""
        from task_reminder.excel_io import ImportReport
        r = ImportReport(total=10, added=5, updated=3, skipped=1, errors=["第 3 行：错误"])
        s = r.summary()
        assert "共读取 10 行" in s
        assert "新增 5" in s
        assert "覆盖 3" in s
        assert "跳过 1" in s
        assert "失败 1" in s
        assert "第 3 行" in s

    def test_import_report_summary_many_errors(self):
        """错误超过 10 条 → 截断显示并提示剩余数量。"""
        from task_reminder.excel_io import ImportReport
        errors = [f"第 {i} 行：错误" for i in range(15)]
        r = ImportReport(total=15, added=0, errors=errors)
        s = r.summary()
        assert "另有 5 条错误未显示" in s

    def test_read_rows_empty_file(self, tmp_path):
        """空 xlsx 文件 → 返回空列表。"""
        from openpyxl import Workbook
        from task_reminder.excel_io import read_rows
        path = str(tmp_path / "empty.xlsx")
        wb = Workbook()
        wb.active  # 空表
        wb.save(path)
        rows = read_rows(path)
        assert rows == []


# ===========================================================================
# 功能测试：widgets.py — 分页栏与确认弹窗
# ===========================================================================
class TestPaginationBarAdvanced:
    """PaginationBar 高级场景：跳页、零条数、末页边界。"""

    def test_jump_to_page(self, qtbot):
        """跳页输入框 → 发出 page_changed 信号。"""
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(1000, 1, 200)  # 5 页
        got = []
        bar.page_changed.connect(got.append)
        bar.spin_page.setValue(3)
        bar._on_jump()
        assert got == [3]
        assert bar.page == 3

    def test_zero_total(self, qtbot):
        """0 条数据 → 显示 1 页，按钮全禁用。"""
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(0, 1, 200)
        assert not bar.btn_next.isEnabled()
        assert not bar.btn_prev.isEnabled()

    def test_last_page(self, qtbot):
        """末页 → 下一页禁用、上一页可用。"""
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(400, 2, 200)  # 2 页
        bar._go(2)  # 到末页
        bar.update_info(400, bar.page, 200)
        assert not bar.btn_next.isEnabled()
        assert bar.btn_prev.isEnabled()

    def test_page_info_text(self, qtbot):
        """分页信息文本包含总条数和页码。"""
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        bar.update_info(450, 2, 200)
        text = bar.lbl_info.text()
        assert "450" in text
        assert "2" in text
        assert "3" in text  # 总页数

    def test_size_menu_options(self, qtbot):
        """每页条数菜单有 4 个选项。"""
        from task_reminder.ui.widgets import PaginationBar
        bar = PaginationBar()
        qtbot.addWidget(bar)
        actions = bar._menu.actions()
        assert len(actions) == 4
        texts = [a.text() for a in actions]
        assert "每页 50" in texts
        assert "每页 100" in texts
        assert "每页 200" in texts
        assert "每页 500" in texts


class TestConfirmDialog:
    """confirm 函数：中文确认弹窗（真实执行 confirm，仅 stub 掉模态 exec）。"""

    def test_confirm_accept(self, qtbot, monkeypatch):
        """用户点'确定' → 返回 True。"""
        from PyQt6.QtWidgets import QMessageBox
        from task_reminder.ui.widgets import confirm
        # exec 不弹窗阻塞；clickedButton 模拟用户点击 AcceptRole 按钮
        def click_accept(self):
            return next(b for b in self.buttons()
                        if self.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole)
        monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
        monkeypatch.setattr(QMessageBox, "clickedButton", click_accept)
        assert confirm(None, "测试标题", "确定吗？") is True

    def test_confirm_reject(self, qtbot, monkeypatch):
        """用户点'取消' → 返回 False。"""
        from PyQt6.QtWidgets import QMessageBox
        from task_reminder.ui.widgets import confirm
        def click_reject(self):
            return next(b for b in self.buttons()
                        if self.buttonRole(b) == QMessageBox.ButtonRole.RejectRole)
        monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
        monkeypatch.setattr(QMessageBox, "clickedButton", click_reject)
        assert confirm(None, "测试标题", "确定吗？") is False

    def test_confirm_has_chinese_buttons(self, qtbot, monkeypatch):
        """弹窗按钮文案为中文'确定/取消'（而非 Qt 默认 Yes/No）。"""
        from PyQt6.QtWidgets import QMessageBox
        from task_reminder.ui.widgets import confirm
        captured = {}
        def fake_exec(self):
            captured["texts"] = [b.text() for b in self.buttons()]
            return None
        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        confirm(None, "标题", "内容")
        assert "确定" in captured["texts"]
        assert "取消" in captured["texts"]


# ===========================================================================
# 集成测试：search_bar.py — 搜索栏高级功能
# ===========================================================================
class TestSearchBarAdvanced:
    """SearchBar：重置、徽章、条件往返。"""

    def test_reset_clears_all(self, qtbot):
        """reset → 所有条件清空。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        bar.set_criteria({"keyword": "测试", "content_kw": "内容",
                          "assignee": "张三", "statuses": ["未开始"]})
        bar.reset()
        c = bar.criteria()
        assert "keyword" not in c
        assert "content_kw" not in c
        assert "assignee" not in c
        assert "statuses" not in c

    def test_set_criteria_roundtrip(self, qtbot):
        """set_criteria → criteria 往返一致。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        original = {"keyword": "报告", "content_kw": "季度",
                    "assignee": "李四", "statuses": ["进行中", "已完成"]}
        bar.set_criteria(original)
        c = bar.criteria()
        assert c["keyword"] == "报告"
        assert c["content_kw"] == "季度"
        assert c["assignee"] == "李四"
        assert set(c["statuses"]) == {"进行中", "已完成"}

    def test_adv_keys_in_use_empty(self, qtbot):
        """无高级条件 → adv_keys_in_use 返回空列表。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        assert bar.adv_keys_in_use() == []

    def test_adv_keys_in_use_multiple(self, qtbot):
        """多个高级条件 → adv_keys_in_use 返回对应列表。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        bar.set_criteria({"content_kw": "内容", "assignee": "张三", "statuses": ["未开始"]})
        keys = bar.adv_keys_in_use()
        assert "content_kw" in keys
        assert "assignee" in keys
        assert "statuses" in keys
        assert len(keys) == 3

    def test_active_badge_hidden_when_panel_open(self, qtbot):
        """高级面板展开时 → 徽章隐藏。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        bar.set_criteria({"content_kw": "内容"})
        bar.btn_advanced.setChecked(True)  # 展开面板
        assert not bar.btn_active.isVisibleTo(bar)

    def test_active_badge_visible_when_panel_closed(self, qtbot):
        """有高级条件且面板收起 → 徽章可见。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        bar.show()
        bar.set_criteria({"content_kw": "内容"})
        bar.btn_advanced.setChecked(False)  # 收起面板
        QApplication.processEvents()
        assert bar.btn_active.isVisibleTo(bar)

    def test_debounce_emits_changed(self, qtbot):
        """文本变化 → 300ms 防抖窗口内不触发，窗口后发出 changed 信号。"""
        from PyQt6.QtTest import QTest
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        got = []
        bar.changed.connect(lambda c: got.append(c))
        bar.edit_keyword.setText("搜索词")
        QTest.qWait(150)  # 300ms 防抖窗口内
        assert len(got) == 0
        QTest.qWait(400)  # 跨过防抖窗口
        assert len(got) == 1
        assert got[0].get("keyword") == "搜索词"

    def test_debounce_coalesces_rapid_input(self, qtbot):
        """连续快速输入（窗口内）→ 防抖合并为一次信号。"""
        from PyQt6.QtTest import QTest
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        got = []
        bar.changed.connect(lambda c: got.append(c))
        for ch in "连续输入":
            bar.edit_keyword.setText(bar.edit_keyword.text() + ch)
            QTest.qWait(50)  # 每次击键间隔 < 300ms，定时器持续重启
        assert len(got) == 0  # 输入过程中不触发
        QTest.qWait(400)
        assert len(got) == 1  # 停顿后合并为一次
        assert got[0].get("keyword") == "连续输入"

    def test_both_date_ranges_independent(self, qtbot):
        """创建时间和截止时间范围独立开关（日期始终可编辑，复选框控制是否生效）。"""
        from task_reminder.ui.search_bar import SearchBar
        bar = SearchBar()
        qtbot.addWidget(bar)
        # 日期始终可编辑
        assert bar._date_ranges["deadline"]["lo"].isEnabled()
        assert bar._date_ranges["created"]["lo"].isEnabled()
        # 只限定截止时间范围并设置日期
        bar._date_ranges["deadline"]["chk"].setChecked(True)
        bar._date_ranges["deadline"]["lo"].setDate(QDate(2026, 9, 1))
        c = bar.criteria()
        assert "deadline_from" in c
        assert "created_from" not in c
        # 再限定创建时间范围并设置日期
        bar._date_ranges["created"]["chk"].setChecked(True)
        bar._date_ranges["created"]["lo"].setDate(QDate(2026, 9, 1))
        c = bar.criteria()
        assert "created_from" in c
        assert "deadline_from" in c
        # 取消限定不影响日期编辑器可用性
        bar._date_ranges["deadline"]["chk"].setChecked(False)
        assert bar._date_ranges["deadline"]["lo"].isEnabled()
        assert "deadline_from" not in bar.criteria()


# ===========================================================================
# 集成测试：task_dialog.py — 时间预设与联动
# ===========================================================================
class TestTaskDialogAdvanced:
    """TaskDialog：时间快捷预设、备注截断、编辑回填。"""

    def test_apply_preset_deadline(self, qtbot):
        """截止时间快捷预设 → 正确应用。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        tomorrow_9 = (datetime.now() + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0)
        dlg._apply_preset(dlg.dt_deadline, True, tomorrow_9)
        new_dt = dlg.dt_deadline.dateTime().toPyDateTime()
        assert new_dt.hour == 9
        assert new_dt.date() == tomorrow_9.date()

    def test_apply_preset_reminder_30min(self, qtbot):
        """提醒时间'30分钟后'预设 → 正确应用。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        from datetime import datetime, timedelta
        now = datetime.now().replace(second=0, microsecond=0)
        preset = now + timedelta(minutes=30)
        dlg._apply_preset(dlg.dt_reminder, False, preset)
        new_dt = dlg.dt_reminder.dateTime().toPyDateTime()
        assert new_dt >= now + timedelta(minutes=29)

    def test_apply_preset_reminder_before_deadline(self, qtbot):
        """提醒预设'截止前1小时' → 基于截止时间计算。"""
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.dt_deadline.setDateTime(QDateTime(2026, 12, 31, 18, 0))
        # dt=None 触发"截止前1小时"逻辑
        dlg._apply_preset(dlg.dt_reminder, False, None)
        reminder = dlg.dt_reminder.dateTime().toPyDateTime()
        # 应为截止 - 1小时，且不早于现在
        assert reminder.hour == 17

    def test_deadline_before_reminder_auto_moves_reminder(self, qtbot):
        """截止时间改到提醒之前 → 提醒自动前移。"""
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 10, 10, 0))
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 10, 9, 0))  # 截止 < 提醒
        # 提醒应被自动调到 08:00
        assert dlg.dt_reminder.dateTime() == QDateTime(2026, 9, 10, 8, 0)

    def test_reminder_after_deadline_auto_moves_deadline(self, qtbot):
        """提醒时间改到截止之后 → 截止自动后移。"""
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 10, 9, 0))
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 10, 10, 0))  # 提醒 > 截止
        # 截止应被自动调到 11:00
        assert dlg.dt_deadline.dateTime() == QDateTime(2026, 9, 10, 11, 0)

    def test_notes_truncation(self, qtbot):
        """备注超过最大长度 → 截断。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        long_text = "字" * (NOTES_MAX + 100)
        dlg.edit_notes.setPlainText(long_text)
        dlg._on_notes_changed()
        assert len(dlg.edit_notes.toPlainText()) == NOTES_MAX
        assert str(NOTES_MAX) in dlg.lbl_notes.text()

    def test_load_existing_task(self, qtbot):
        """编辑已有任务 → 字段正确回填。"""
        from task_reminder.ui.task_dialog import TaskDialog
        tid = mk(name="编辑测试", assignee="王五", content="<b>富文本</b>",
                 notes="备注内容", status=TaskStatus.IN_PROGRESS)
        task = repo.get_task(tid)
        dlg = TaskDialog(editing_task=task)
        qtbot.addWidget(dlg)
        dlg.show()
        QApplication.processEvents()
        assert dlg.edit_name.text() == "编辑测试"
        assert dlg.edit_assignee.text() == "王五"
        assert "富文本" in dlg.edit_content.toHtml()
        # QComboBox 在 offscreen 模式下用 index 更可靠
        idx = dlg.cmb_status.findText(TaskStatus.IN_PROGRESS)
        assert idx >= 0
        assert dlg.cmb_status.currentIndex() == idx
        assert dlg.edit_notes.toPlainText() == "备注内容"

    def test_content_count_displayed(self, qtbot):
        """内容字数实时显示。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_content.setPlainText("12345")
        dlg._on_content_changed()
        assert "5" in dlg.lbl_count.text()
        assert str(CONTENT_MAX) in dlg.lbl_count.text()

    def test_content_over_limit_shows_error(self, qtbot):
        """内容超过 5000 字 → 计数标红。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_content.setPlainText("字" * (CONTENT_MAX + 1))
        dlg._on_content_changed()
        assert "#DC2626" in dlg.lbl_count.styleSheet()

    def test_edit_task_returns_true_on_accept(self, qtbot, monkeypatch):
        """TaskDialog.edit 在 exec 返回 1 时 → 返回 True。"""
        from task_reminder.ui.task_dialog import TaskDialog
        tid = mk()
        task = repo.get_task(tid)
        # 模拟 exec 返回 1
        monkeypatch.setattr(TaskDialog, "exec", lambda self: 1)
        assert TaskDialog.edit(None, task) is True

    def test_edit_task_returns_false_on_reject(self, qtbot, monkeypatch):
        """TaskDialog.edit 在 exec 返回 0 时 → 返回 False。"""
        from task_reminder.ui.task_dialog import TaskDialog
        tid = mk()
        task = repo.get_task(tid)
        monkeypatch.setattr(TaskDialog, "exec", lambda self: 0)
        assert TaskDialog.edit(None, task) is False

    def test_default_times_reminder_before_deadline(self, qtbot):
        """新建对话框默认时间 → 提醒早于截止。"""
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        assert dlg.dt_reminder.dateTime() < dlg.dt_deadline.dateTime()

    def test_validate_returns_null_on_valid(self, qtbot):
        """合法输入 → _validate 返回 None，保存按钮可用。"""
        from task_reminder.ui.task_dialog import TaskDialog
        from PyQt6.QtCore import QDateTime
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("合法任务")
        dlg.edit_assignee.setText("张三")
        dlg.edit_content.setPlainText("内容")
        dlg.dt_deadline.setDateTime(QDateTime(2026, 9, 10, 10, 0))
        dlg.dt_reminder.setDateTime(QDateTime(2026, 9, 9, 9, 0))
        assert dlg._validate() is None
        assert dlg.btn_ok.isEnabled()


# ===========================================================================
# 功能测试：dashboard_page.py — 看板统计与卡片
# ===========================================================================
class TestDashboardPage:
    """DashboardPage：统计卡片点击、数据刷新、柱状图。"""

    def test_stat_card_click_signal(self, qtbot):
        """StatCard 点击 → 发出 clicked 信号。"""
        from PyQt6.QtCore import QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent
        from task_reminder.ui.dashboard_page import StatCard
        card = StatCard("总数", "blue", key="total")
        qtbot.addWidget(card)
        card.show()
        got = []
        card.clicked.connect(got.append)
        # 模拟鼠标按下事件（不能传 None，否则 C++ 层 access violation）
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        card.mousePressEvent(ev)
        assert got == ["total"]

    def test_refresh_updates_card_values(self, qtbot):
        """refresh → 统计卡片值更新。"""
        from task_reminder.ui.dashboard_page import DashboardPage
        mk(status=TaskStatus.NOT_STARTED)
        mk(status=TaskStatus.IN_PROGRESS)
        mk(status=TaskStatus.DONE)
        page = DashboardPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.card_total.lbl_value.text() == "3"
        assert page.card_notstarted.lbl_value.text() == "1"
        assert page.card_inprogress.lbl_value.text() == "1"
        assert page.card_done.lbl_value.text() == "1"

    def test_refresh_shows_overdue(self, qtbot):
        """refresh → 过期卡片显示正确数量。"""
        from task_reminder.ui.dashboard_page import DashboardPage
        mk(deadline=fmt(datetime.now() - timedelta(days=1)),
           reminder=fmt(datetime.now() - timedelta(days=2)))
        page = DashboardPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.card_overdue.lbl_value.text() == "1"

    def test_refresh_empty_lists(self, qtbot):
        """无任务 → 即将提醒和已过期列表显示提示文字。"""
        from task_reminder.ui.dashboard_page import DashboardPage
        page = DashboardPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.list_upcoming["list"].count() == 1
        assert "暂无" in page.list_upcoming["list"].item(0).text()
        assert page.list_overdue["list"].count() == 1
        assert "没有过期" in page.list_overdue["list"].item(0).text()

    def test_refresh_populates_upcoming_list(self, qtbot):
        """有即将提醒的任务 → 列表显示任务摘要。"""
        from task_reminder.ui.dashboard_page import DashboardPage
        mk(name="即将提醒任务", assignee="赵六",
           reminder=fmt(datetime.now() + timedelta(hours=2)))
        page = DashboardPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.list_upcoming["list"].count() == 1
        text = page.list_upcoming["list"].item(0).text()
        assert "即将提醒任务" in text
        assert "赵六" in text

    def test_refresh_populates_overdue_list(self, qtbot):
        """有过期任务 → 列表显示。"""
        from task_reminder.ui.dashboard_page import DashboardPage
        mk(name="过期任务", assignee="钱七",
           deadline=fmt(datetime.now() - timedelta(days=1)),
           reminder=fmt(datetime.now() - timedelta(days=2)))
        page = DashboardPage()
        qtbot.addWidget(page)
        page.refresh()
        assert page.list_overdue["list"].count() == 1
        text = page.list_overdue["list"].item(0).text()
        assert "过期任务" in text
        assert "钱七" in text

    def test_bar_chart_set_data(self, qtbot):
        """BarChart.set_data → 触发重绘。"""
        from task_reminder.ui.dashboard_page import BarChart
        chart = BarChart()
        qtbot.addWidget(chart)
        chart.set_data([("未开始", 3, "#64748B"), ("进行中", 5, "#2563EB")])
        assert len(chart._data) == 2
        assert chart._data[0][1] == 3

    def test_bar_chart_empty_data(self, qtbot):
        """BarChart 空数据 → 不崩溃。"""
        from task_reminder.ui.dashboard_page import BarChart
        chart = BarChart()
        qtbot.addWidget(chart)
        chart.set_data([])
        assert chart._data == []


# ===========================================================================
# 集成测试：repository.py — 复杂查询与边界
# ===========================================================================
class TestRepositoryAdvanced:
    """Repository 高级查询：复合条件、空结果、排序边界。"""

    def test_search_combined_criteria(self):
        """复合条件：名称关键词 + 执行人 + 状态。"""
        mk(name="季度报告", assignee="张三", status=TaskStatus.NOT_STARTED)
        mk(name="季度报告", assignee="李四", status=TaskStatus.NOT_STARTED)
        mk(name="季度报告", assignee="张三", status=TaskStatus.DONE)
        rows, total = repo.list_tasks(criteria={
            "keyword": "季度", "assignee": "张三", "statuses": [TaskStatus.NOT_STARTED]
        })
        assert total == 1
        assert rows[0].assignee == "张三"
        assert rows[0].status == TaskStatus.NOT_STARTED

    def test_search_content_and_notes(self):
        """内容关键词同时搜索内容和备注。"""
        mk(name="任务A", content="项目计划", notes="")
        mk(name="任务B", content="其他", notes="项目计划在备注中")
        rows, total = repo.list_tasks(criteria={"content_kw": "项目计划"})
        assert total == 2

    def test_search_multi_term_content_and(self):
        """内容多词 AND 逻辑。"""
        mk(name="任务A", content="季度 报告 数据")
        mk(name="任务B", content="季度 其他")
        rows, total = repo.list_tasks(criteria={"content_kw": "季度 报告"})
        assert total == 1
        assert rows[0].name == "任务A"

    def test_search_empty_criteria_returns_all(self):
        """空条件 → 返回全部。"""
        mk()
        mk()
        rows, total = repo.list_tasks(criteria={})
        assert total >= 2

    def test_search_nonexistent_keyword(self):
        """搜索不存在的关键词 → 0 条。"""
        mk(name="存在任务")
        rows, total = repo.list_tasks(criteria={"keyword": "不存在的关键词"})
        assert total == 0
        assert rows == []

    def test_sort_by_assignee(self):
        """按执行人升序排序（SQLite 按 Unicode 码点排序）。"""
        mk(name="A", assignee="张三")
        mk(name="B", assignee="李四")
        rows, _ = repo.list_tasks(sort_key="assignee", sort_dir="asc", page_size=10)
        names = [r.assignee for r in rows[:2]]
        # 码点序：张(U+5F20) < 李(U+674E)，与 Python sorted 的 Unicode 序一致
        assert names == sorted(names)
        assert names == ["张三", "李四"]

    def test_sort_by_name(self):
        """按名称排序。"""
        mk(name="乙任务")
        mk(name="甲任务")
        rows, _ = repo.list_tasks(sort_key="name", sort_dir="asc", page_size=10)
        assert rows[0].name <= rows[1].name

    def test_sort_invalid_key_falls_back(self):
        """无效排序键 → 回退到 created_at。"""
        mk()
        rows, total = repo.list_tasks(sort_key="invalid_key", sort_dir="asc")
        assert total >= 1  # 不崩溃即可

    def test_pagination_beyond_last_page(self):
        """请求超出总页数 → 返回空列表。"""
        mk()
        rows, total = repo.list_tasks(page=99, page_size=10)
        assert len(rows) == 0
        assert total >= 1

    def test_tasks_by_ids_empty(self):
        """空 id 列表 → 空结果。"""
        assert repo.tasks_by_ids([]) == []

    def test_tasks_by_ids_multiple(self):
        """多 id 查询 → 返回对应任务。"""
        t1 = mk(name="任务1")
        t2 = mk(name="任务2")
        result = repo.tasks_by_ids([t1, t2])
        assert len(result) == 2
        names = {t.name for t in result}
        assert "任务1" in names and "任务2" in names

    def test_tasks_by_ids_nonexistent(self):
        """不存在的 id → 不在结果中。"""
        t1 = mk()
        result = repo.tasks_by_ids([t1, 99999])
        assert len(result) == 1

    def test_set_status_invalid_raises(self):
        """set_status 传入无效状态 → ValidationError。"""
        tid = mk()
        with pytest.raises(repo.ValidationError):
            repo.set_status(tid, "无效状态")

    def test_mark_triggered_nonexistent_returns_none(self):
        """mark_triggered 传入不存在的 id → None。"""
        assert repo.mark_triggered(99999) is None

    def test_update_task_status_changed_timestamp(self):
        """update_task 状态变化 → status_changed_at 更新。"""
        tid = mk(status=TaskStatus.NOT_STARTED)
        old_ts = repo.get_task(tid).status_changed_at
        assert old_ts == ""
        t = repo.get_task(tid)
        repo.update_task(tid, name=t.name, assignee=t.assignee, content=t.content,
                         deadline=t.deadline, reminder_time=t.reminder_time,
                         status=TaskStatus.IN_PROGRESS, notes=t.notes)
        new_ts = repo.get_task(tid).status_changed_at
        assert new_ts != ""

    def test_update_task_same_status_no_timestamp_change(self):
        """update_task 状态不变 → status_changed_at 不刷新。"""
        tid = mk(status=TaskStatus.IN_PROGRESS)
        t = repo.get_task(tid)
        first_ts = t.status_changed_at
        assert first_ts != ""  # IN_PROGRESS 创建时即记录时间戳
        repo.update_task(tid, name=t.name, assignee=t.assignee, content=t.content,
                         deadline=t.deadline, reminder_time=t.reminder_time,
                         status=TaskStatus.IN_PROGRESS, notes="新备注")
        assert repo.get_task(tid).status_changed_at == first_ts

    def test_delete_tasks_empty_list(self):
        """空 id 列表 → 返回 0。"""
        assert repo.delete_tasks([]) == 0

    def test_find_duplicate_no_match(self):
        """无重复 → None。"""
        mk(name="唯一任务", assignee="张三", deadline="2026-09-10 10:00")
        assert repo.find_duplicate("其他任务", "张三", "2026-09-10 10:00") is None

    def test_list_history_pagination(self):
        """历史分页：多页返回正确数量。"""
        tid = mk()
        for _ in range(5):
            repo.mark_triggered(tid)
        logs, total = repo.list_history(page=1, page_size=2)
        assert len(logs) == 2
        assert total >= 5
        logs2, _ = repo.list_history(page=2, page_size=2)
        assert len(logs2) == 2

    def test_list_history_date_filter(self):
        """历史按日期范围过滤。"""
        tid = mk()
        repo.mark_triggered(tid)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        logs, total = repo.list_history(start=now)
        assert total >= 1
        logs2, total2 = repo.list_history(start="2030-01-01 00:00")
        assert total2 == 0

    def test_stats_empty_db(self):
        """空数据库统计 → 全 0。"""
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        s = repo.stats()
        assert s["total"] == 0
        assert s["overdue"] == 0
        assert s["due_week"] == 0
        assert all(v == 0 for v in s["by_status"].values())

    def test_upcoming_reminders_limit(self):
        """upcoming_reminders 限制返回数量。"""
        for i in range(5):
            mk(name=f"即将{i}", reminder=fmt(datetime.now() + timedelta(hours=i + 1)))
        result = repo.upcoming_reminders(limit=3)
        assert len(result) == 3

    def test_overdue_tasks_excludes_done(self):
        """overdue_tasks 不包含已完成任务。"""
        mk(name="过期未完成", deadline=fmt(datetime.now() - timedelta(days=1)),
           reminder=fmt(datetime.now() - timedelta(days=2)), status=TaskStatus.NOT_STARTED)
        mk(name="过期已完成", deadline=fmt(datetime.now() - timedelta(days=1)),
           reminder=fmt(datetime.now() - timedelta(days=2)), status=TaskStatus.DONE)
        result = repo.overdue_tasks(10)
        names = [t.name for t in result]
        assert "过期未完成" in names
        assert "过期已完成" not in names

    def test_all_tasks_with_criteria(self):
        """all_tasks 支持条件过滤。"""
        mk(name="匹配任务", assignee="张三")
        mk(name="不匹配", assignee="李四")
        result = repo.all_tasks(criteria={"assignee": "张三"})
        assert len(result) == 1
        assert result[0].assignee == "张三"
