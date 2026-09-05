"""数据仓库层：任务/提醒历史/保存的搜索条件的全部数据操作。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

from . import db, app_config
from .models import (STATUS_SORT_ORDER, Task, TaskStatus, ReminderLog, fmt, html_to_plain, parse)

# ---------------------------------------------------------------------------
# 排序键白名单 → SQL
_SORT_SQL = {
    "deadline": "deadline",
    "reminder_time": "reminder_time",
    "assignee": "assignee COLLATE NOCASE",
    "name": "name COLLATE NOCASE",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "status": "CASE status WHEN '未开始' THEN 0 WHEN '进行中' THEN 1 WHEN '已完成' THEN 2 ELSE 3 END",
}


def _now() -> str:
    return fmt(datetime.now())


# ---------------------------------------------------------------------------
# 校验
class ValidationError(ValueError):
    """字段校验失败。"""


def validate_task(name: str, assignee: str, content: str, deadline: str,
                  reminder_time: str, *, task_id: Optional[int] = None) -> None:
    from .models import NAME_MIN, NAME_MAX, CONTENT_MAX, plain_len
    name = (name or "").strip()
    assignee = (assignee or "").strip()
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        raise ValidationError(f"任务名称长度须在 {NAME_MIN}-{NAME_MAX} 字符之间")
    if not (NAME_MIN <= len(assignee) <= NAME_MAX):
        raise ValidationError(f"执行人姓名长度须在 {NAME_MIN}-{NAME_MAX} 字符之间")
    if plain_len(content) > CONTENT_MAX:
        raise ValidationError(f"任务内容最多 {CONTENT_MAX} 字符")
    dl = parse(deadline)
    if not dl:
        raise ValidationError("截止时间无效")
    rt = parse(reminder_time)
    if not rt:
        raise ValidationError("提醒时间无效")
    if rt >= dl:
        raise ValidationError("提醒时间必须早于截止时间")


# ---------------------------------------------------------------------------
# 任务 CRUD
def add_task(name: str, assignee: str, content: str, deadline: str, reminder_time: str,
             status: str = TaskStatus.NOT_STARTED, notes: str = "") -> int:
    validate_task(name, assignee, content, deadline, reminder_time)
    now = _now()
    with db.transaction() as c:
        cur = c.execute(
            "INSERT INTO tasks(name, assignee, content, deadline, reminder_time, status, notes,"
            " triggered, status_changed_at, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (name.strip(), assignee.strip(), content, deadline, reminder_time, status, notes,
             0, now if status != TaskStatus.NOT_STARTED else "", now, now),
        )
        return int(cur.lastrowid)


def update_task(task_id: int, name: str, assignee: str, content: str, deadline: str,
                reminder_time: str, status: str, notes: str) -> None:
    validate_task(name, assignee, content, deadline, reminder_time)
    old = get_task(task_id)
    now = _now()
    status_changed = old is None or old.status != status
    sc_at = (old.status_changed_at or "") if (old and not status_changed) else (now if status_changed else "")
    with db.transaction() as c:
        c.execute(
            "UPDATE tasks SET name=?, assignee=?, content=?, deadline=?, reminder_time=?,"
            " status=?, notes=?, status_changed_at=?, updated_at=? WHERE id=?",
            (name.strip(), assignee.strip(), content, deadline, reminder_time, status, notes,
             sc_at, now, task_id),
        )
    # 状态改为已完成时清除未触发的提醒标记
    if status == TaskStatus.DONE:
        with db.transaction() as c:
            c.execute("UPDATE tasks SET triggered=1 WHERE id=?", (task_id,))


def set_status(task_id: int, status: str) -> None:
    if status not in TaskStatus.ALL:
        raise ValidationError("无效的任务状态")
    update_task(task_id, **_task_kwargs(get_task(task_id)), status=status)


def _task_kwargs(t: Task) -> dict:
    return dict(name=t.name, assignee=t.assignee, content=t.content, deadline=t.deadline,
                reminder_time=t.reminder_time, notes=t.notes)


def delete_task(task_id: int) -> None:
    with db.transaction() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        c.execute("DELETE FROM reminder_history WHERE task_id=?", (task_id,))


def delete_tasks(ids: Iterable[int]) -> int:
    ids = list(ids)
    if not ids:
        return 0
    with db.transaction() as c:
        q = ",".join("?" * len(ids))
        cur = c.execute(f"DELETE FROM tasks WHERE id IN ({q})", ids)
        c.execute(f"DELETE FROM reminder_history WHERE task_id IN ({q})", ids)
        return cur.rowcount


def get_task(task_id: int) -> Optional[Task]:
    row = db.get_conn().execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return Task.from_row(row) if row else None


def find_duplicate(name: str, assignee: str, deadline: str) -> Optional[Task]:
    """导入冲突判定：名称+执行人+截止时间相同视为重复。"""
    row = db.get_conn().execute(
        "SELECT * FROM tasks WHERE name=? AND assignee=? AND deadline=? LIMIT 1",
        (name, assignee, deadline),
    ).fetchone()
    return Task.from_row(row) if row else None


# ---------------------------------------------------------------------------
# 查询/排序/分页
def _criteria_sql(criteria: dict) -> tuple[str, list]:
    where, args = ["1=1"], []
    if criteria.get("assignee"):
        where.append("assignee = ?")
        args.append(criteria["assignee"].strip())
    if criteria.get("keyword"):
        kw = f"%{criteria['keyword'].strip()}%"
        where.append("(name LIKE ? OR content LIKE ? OR notes LIKE ?)")
        args += [kw, kw, kw]
    for col, key in (("created_at", "created"), ("deadline", "deadline"),
                     ("reminder_time", "reminder")):
        lo, hi = criteria.get(f"{key}_from"), criteria.get(f"{key}_to")
        if lo:
            where.append(f"{col} >= ?")
            args.append(str(lo))
        if hi:
            where.append(f"{col} <= ?")
            args.append(str(hi))
    statuses = criteria.get("statuses") or []
    if statuses:
        where.append("status IN (%s)" % ",".join("?" * len(statuses)))
        args += list(statuses)
    return " AND ".join(where), args


def list_tasks(page: int = 1, page_size: Optional[int] = None, sort_key: str = "created_at",
               sort_dir: str = "desc", criteria: Optional[dict] = None) -> tuple[list[Task], int]:
    """分页查询任务。返回 (当前页任务列表, 符合条件的总数)。"""
    page_size = page_size or int(app_config.get("page_size", 200))
    page = max(1, int(page))
    col = _SORT_SQL.get(sort_key, _SORT_SQL["created_at"])
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    where, args = _criteria_sql(criteria or {})
    c = db.get_conn()
    total = c.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", args).fetchone()[0]
    rows = c.execute(
        f"SELECT * FROM tasks WHERE {where} ORDER BY {col} {direction}, id {direction} LIMIT ? OFFSET ?",
        [*args, page_size, (page - 1) * page_size],
    ).fetchall()
    return [Task.from_row(r) for r in rows], int(total)


def all_tasks(criteria: Optional[dict] = None, sort_key: str = "created_at",
              sort_dir: str = "desc") -> list[Task]:
    """不分页全量查询（导出用）。"""
    col = _SORT_SQL.get(sort_key, _SORT_SQL["created_at"])
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    where, args = _criteria_sql(criteria or {})
    rows = db.get_conn().execute(
        f"SELECT * FROM tasks WHERE {where} ORDER BY {col} {direction}, id {direction}",
        args,
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def tasks_by_ids(ids: Iterable[int], sort_key: str = "created_at", sort_dir: str = "desc") -> list[Task]:
    ids = list(ids)
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    rows = db.get_conn().execute(f"SELECT * FROM tasks WHERE id IN ({q})", ids).fetchall()
    return [Task.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# 提醒相关
def due_for_reminder(now: Optional[datetime] = None) -> list[Task]:
    """到提醒时间、未完成且本轮未触发的任务。"""
    now = now or datetime.now()
    rows = db.get_conn().execute(
        "SELECT * FROM tasks WHERE triggered=0 AND status != ? AND reminder_time <= ?"
        " ORDER BY reminder_time ASC",
        (TaskStatus.DONE, fmt(now)),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def mark_triggered(task_id: int, log_snapshot: bool = True) -> Optional[int]:
    """标记已触发并写入提醒历史，返回历史 id。"""
    task = get_task(task_id)
    if task is None:
        return None
    now = _now()
    with db.transaction() as c:
        c.execute("UPDATE tasks SET triggered=1, updated_at=? WHERE id=?", (now, task_id))
        cur = c.execute(
            "INSERT INTO reminder_history(task_id, triggered_at, assignee, content_snapshot,"
            " deadline) VALUES(?,?,?,?,?)",
            (task.id, now, task.assignee, task.content_plain() or task.name, task.deadline),
        )
        return int(cur.lastrowid)


def set_history_response(history_id: int, response: str) -> None:
    with db.transaction() as c:
        c.execute(
            "UPDATE reminder_history SET response=?, responded_at=?, acknowledged=1 WHERE id=?",
            (response, _now(), history_id),
        )


def reset_triggered_for_new_day(now: Optional[datetime] = None) -> int:
    """跨日重置：昨日及更早提醒过但未完成的任务，重置触发标记以便次日再提醒。"""
    now = now or datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with db.transaction() as c:
        cur = c.execute(
            "UPDATE tasks SET triggered=0 WHERE triggered=1 AND status != ? AND reminder_time < ?",
            (TaskStatus.DONE, fmt(today_start)),
        )
        return cur.rowcount


# ---------------------------------------------------------------------------
# 提醒历史
def list_history(page: int = 1, page_size: int = 50, start: str = "", end: str = ""
                 ) -> tuple[list[ReminderLog], int]:
    page = max(1, int(page))
    where, args = ["1=1"], []
    if start:
        where.append("triggered_at >= ?")
        args.append(start)
    if end:
        where.append("triggered_at <= ?")
        args.append(end)
    cond = " AND ".join(where)
    c = db.get_conn()
    total = c.execute(f"SELECT COUNT(*) FROM reminder_history WHERE {cond}", args).fetchone()[0]
    rows = c.execute(
        f"SELECT * FROM reminder_history WHERE {cond} ORDER BY triggered_at DESC, id DESC"
        " LIMIT ? OFFSET ?",
        [*args, page_size, (page - 1) * page_size],
    ).fetchall()
    return [ReminderLog.from_row(r) for r in rows], int(total)


def clear_history() -> int:
    with db.transaction() as c:
        return c.execute("DELETE FROM reminder_history").rowcount


# ---------------------------------------------------------------------------
# 保存的搜索条件
def save_search(name: str, criteria: dict) -> int:
    import json
    with db.transaction() as c:
        cur = c.execute(
            "INSERT INTO saved_searches(name, criteria, created_at) VALUES(?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET criteria=excluded.criteria",
            (name.strip(), json.dumps(criteria, ensure_ascii=False), _now()),
        )
        return int(cur.lastrowid)


def list_searches() -> list[dict]:
    import json
    rows = db.get_conn().execute("SELECT * FROM saved_searches ORDER BY id").fetchall()
    out = []
    for r in rows:
        try:
            criteria = json.loads(r["criteria"])
        except (ValueError, TypeError):
            criteria = {}
        out.append({"id": r["id"], "name": r["name"], "criteria": criteria})
    return out


def delete_search(search_id: int) -> None:
    with db.transaction() as c:
        c.execute("DELETE FROM saved_searches WHERE id=?", (search_id,))


# ---------------------------------------------------------------------------
# 统计（数据看板）
def stats(now: Optional[datetime] = None) -> dict:
    now = now or datetime.now()
    c = db.get_conn()
    total = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    by_status = {s: 0 for s in TaskStatus.ALL}
    for r in c.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"):
        by_status[r["status"]] = r["n"]
    now_s = fmt(now)
    overdue = c.execute(
        "SELECT COUNT(*) FROM tasks WHERE status != ? AND deadline < ?",
        (TaskStatus.DONE, now_s),
    ).fetchone()[0]
    week_end = fmt(now + timedelta(days=7))
    due_week = c.execute(
        "SELECT COUNT(*) FROM tasks WHERE status != ? AND deadline >= ? AND deadline < ?",
        (TaskStatus.DONE, now_s, week_end),
    ).fetchone()[0]
    history_total = c.execute("SELECT COUNT(*) FROM reminder_history").fetchone()[0]
    return {
        "total": int(total),
        "by_status": by_status,
        "overdue": int(overdue),
        "due_week": int(due_week),
        "history_total": int(history_total),
    }


def upcoming_reminders(limit: int = 10) -> list[Task]:
    now_s = _now()
    rows = db.get_conn().execute(
        "SELECT * FROM tasks WHERE status != ? AND reminder_time >= ?"
        " ORDER BY reminder_time ASC LIMIT ?",
        (TaskStatus.DONE, now_s, limit),
    ).fetchall()
    return [Task.from_row(r) for r in rows]


def overdue_tasks(limit: int = 10) -> list[Task]:
    now_s = _now()
    rows = db.get_conn().execute(
        "SELECT * FROM tasks WHERE status != ? AND deadline < ? ORDER BY deadline ASC LIMIT ?",
        (TaskStatus.DONE, now_s, limit),
    ).fetchall()
    return [Task.from_row(r) for r in rows]
