"""SQLite 连接、schema 创建与迁移。"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_conn: Optional[sqlite3.Connection] = None
_db_path: str = ""


def default_db_path() -> str:
    """默认数据库路径：%APPDATA%/TaskReminder/tasks.db"""
    base = os.environ.get("APPDATA") or str(Path.home())
    return str(Path(base) / "TaskReminder" / "tasks.db")


def init(db_path: Optional[str] = None) -> sqlite3.Connection:
    """初始化数据库连接与 schema（可重复调用）。"""
    global _conn, _db_path
    _db_path = db_path or default_db_path()
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
    if _conn is not None:
        try:
            _conn.close()
        except sqlite3.Error:
            pass
    _conn = sqlite3.connect(_db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(_conn)
    return _conn


def get_conn() -> sqlite3.Connection:
    if _conn is None:
        init()
    return _conn


def close() -> None:
    global _conn
    if _conn is not None:
        try:
            _conn.commit()
            _conn.close()
        except sqlite3.Error:
            pass
        _conn = None


@contextmanager
def transaction():
    c = get_conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def ensure_schema(c: sqlite3.Connection) -> None:
    cur = c.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
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
        CREATE TABLE IF NOT EXISTS reminder_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            triggered_at TEXT NOT NULL DEFAULT '',
            assignee TEXT NOT NULL DEFAULT '',
            content_snapshot TEXT NOT NULL DEFAULT '',
            deadline TEXT NOT NULL DEFAULT '',
            response TEXT NOT NULL DEFAULT '',
            responded_at TEXT NOT NULL DEFAULT '',
            acknowledged INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            criteria TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    # v1.0 → v2.0 迁移：增量列
    task_cols = {r[1] for r in cur.execute("PRAGMA table_info(tasks)")}
    if "name" not in task_cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "status_changed_at" not in task_cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN status_changed_at TEXT NOT NULL DEFAULT ''")
    hist_cols = {r[1] for r in cur.execute("PRAGMA table_info(reminder_history)")}
    if "response" not in hist_cols:
        cur.execute("ALTER TABLE reminder_history ADD COLUMN response TEXT NOT NULL DEFAULT ''")
    if "responded_at" not in hist_cols:
        cur.execute("ALTER TABLE reminder_history ADD COLUMN responded_at TEXT NOT NULL DEFAULT ''")

    cur.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON tasks (triggered, reminder_time);
        CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks (deadline);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
        CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee);
        CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks (name);
        CREATE INDEX IF NOT EXISTS idx_history_triggered ON reminder_history (triggered_at);
        CREATE INDEX IF NOT EXISTS idx_history_task ON reminder_history (task_id);
        """
    )
    c.commit()


def db_path() -> str:
    return _db_path
