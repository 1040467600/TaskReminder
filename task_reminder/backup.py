"""备份恢复：JSON 导出/导入（任务 + 提醒历史 + 佐证图片）。"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from pathlib import Path

from . import db, repository
from .models import fmt, html_to_plain

FORMAT_VERSION = 3


def export_json(path: str) -> int:
    """导出全部任务、提醒历史与佐证图片（图片以 base64 内嵌）。返回任务数。"""
    c = db.get_conn()
    tasks = [dict(r) for r in c.execute("SELECT * FROM tasks").fetchall()]
    history = [dict(r) for r in c.execute("SELECT * FROM reminder_history").fetchall()]
    images = []
    for r in c.execute("SELECT * FROM task_images ORDER BY id ASC").fetchall():
        item = dict(r)
        item["data_b64"] = None
        img_file = repository.images_dir() / item["stored_name"]
        try:
            item["data_b64"] = base64.b64encode(img_file.read_bytes()).decode("ascii")
        except OSError as e:
            logging.getLogger("task_reminder").warning(
                "备份时图片文件缺失/不可读：%s（%s）", img_file, e)
        images.append(item)
    payload = {
        "format": "task_reminder_backup",
        "version": FORMAT_VERSION,
        "exported_at": fmt(datetime.now()),
        "tasks": tasks,
        "history": history,
        "images": images,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(tasks)


def import_json(path: str) -> tuple[int, int]:
    """导入 JSON 备份（按 id upsert，含佐证图片文件还原）。返回 (任务数, 历史数)。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "task_reminder_backup":
        raise ValueError("不是有效的任务提醒备份文件")
    c = db.get_conn()
    n_tasks = n_hist = 0
    with db.transaction():
        for t in data.get("tasks", []):
            t = dict(t)
            # 兼容旧备份：按导入内容重算纯文本列
            t["content_plain"] = html_to_plain(t.get("content") or "")
            c.execute(
                "INSERT INTO tasks(id, name, assignee, content, content_plain, deadline,"
                " reminder_time, status, notes, triggered, status_changed_at, created_at, updated_at)"
                " VALUES(:id, :name, :assignee, :content, :content_plain, :deadline,"
                " :reminder_time, :status, :notes, :triggered, :status_changed_at,"
                " :created_at, :updated_at)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name, assignee=excluded.assignee,"
                " content=excluded.content, content_plain=excluded.content_plain,"
                " deadline=excluded.deadline,"
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
        for im in data.get("images", []):   # v3 起备份内嵌佐证图片
            c.execute(
                "INSERT INTO task_images(id, task_id, filename, stored_name, added_at)"
                " VALUES(:id, :task_id, :filename, :stored_name, :added_at)"
                " ON CONFLICT(id) DO UPDATE SET task_id=excluded.task_id,"
                " filename=excluded.filename, stored_name=excluded.stored_name,"
                " added_at=excluded.added_at",
                im,
            )
            blob = im.get("data_b64")
            if blob:
                try:
                    target = repository.images_dir() / im["stored_name"]
                    target.write_bytes(base64.b64decode(blob))
                except (OSError, ValueError) as e:
                    logging.getLogger("task_reminder").warning(
                        "恢复时图片写入失败：%s（%s）", im.get("stored_name"), e)
    return n_tasks, n_hist
