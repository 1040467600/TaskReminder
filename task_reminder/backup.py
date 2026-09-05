"""备份恢复：JSON 导出/导入（任务 + 提醒历史）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import db
from .models import fmt

FORMAT_VERSION = 2


def export_json(path: str) -> int:
    """导出全部任务与提醒历史。返回任务数。"""
    c = db.get_conn()
    tasks = [dict(r) for r in c.execute("SELECT * FROM tasks").fetchall()]
    history = [dict(r) for r in c.execute("SELECT * FROM reminder_history").fetchall()]
    payload = {
        "format": "task_reminder_backup",
        "version": FORMAT_VERSION,
        "exported_at": fmt(datetime.now()),
        "tasks": tasks,
        "history": history,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(tasks)


def import_json(path: str) -> tuple[int, int]:
    """导入 JSON 备份（按 id upsert）。返回 (任务数, 历史数)。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "task_reminder_backup":
        raise ValueError("不是有效的任务提醒备份文件")
    c = db.get_conn()
    n_tasks = n_hist = 0
    with db.transaction():
        for t in data.get("tasks", []):
            c.execute(
                "INSERT INTO tasks(id, name, assignee, content, deadline, reminder_time, status,"
                " notes, triggered, status_changed_at, created_at, updated_at)"
                " VALUES(:id, :name, :assignee, :content, :deadline, :reminder_time, :status,"
                " :notes, :triggered, :status_changed_at, :created_at, :updated_at)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name, assignee=excluded.assignee,"
                " content=excluded.content, deadline=excluded.deadline,"
                " reminder_time=excluded.reminder_time, status=excluded.status,"
                " notes=excluded.notes, triggered=excluded.triggered,"
                " status_changed_at=excluded.status_changed_at, updated_at=excluded.updated_at",
                t,
            )
            n_tasks += 1
        for h in data.get("history", []):
            c.execute(
                "INSERT INTO reminder_history(id, task_id, triggered_at, assignee,"
                " content_snapshot, deadline, response, responded_at, acknowledged)"
                " VALUES(:id, :task_id, :triggered_at, :assignee, :content_snapshot,"
                " :deadline, :response, :responded_at, :acknowledged)"
                " ON CONFLICT(id) DO UPDATE SET response=excluded.response,"
                " responded_at=excluded.responded_at, acknowledged=excluded.acknowledged",
                h,
            )
            n_hist += 1
    return n_tasks, n_hist
