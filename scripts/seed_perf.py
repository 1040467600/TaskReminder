"""Seed performance test data into a dedicated SQLite database.

Usage:
    python scripts\\seed_perf.py --n 10000
    python scripts\\seed_perf.py --n 100000 --db path\\to\\perf.db
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSIGNEES = ["张伟", "李娜", "王强", "刘洋", "陈静", "杨帆", "赵磊", "黄敏", "周杰", "吴霞"]
STATUSES = ["未开始", "进行中", "已完成"]
WORDS = ["季度报表", "客户回访", "系统巡检", "合同归档", "需求评审", "版本发布", "数据备份",
         "安全审计", "培训安排", "设备维护", "预算核算", "供应商对接"]


def main() -> int:
    parser = argparse.ArgumentParser(description="seed perf data")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--db", type=str, default=str(ROOT / ".tmp_test" / "perf_100k" / "tasks.db"))
    args = parser.parse_args()

    os.environ["APPDATA"] = str(Path(args.db).parent)
    from task_reminder import db, repository

    db.init(args.db)
    conn: sqlite3.Connection = db.get_conn()

    # wipe previous perf data
    conn.execute("DELETE FROM tasks")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")

    now = datetime.now()
    rows = []
    for i in range(1, args.n + 1):
        created = now - timedelta(minutes=random.randint(0, args.n * 2))
        deadline = created + timedelta(hours=random.randint(1, 24 * 30))
        if random.random() < 0.05:  # 5% already overdue
            deadline = now - timedelta(minutes=random.randint(1, 60 * 24))
        remind = deadline - timedelta(minutes=random.choice([5, 15, 30, 60, 1440]))
        status = random.choices(STATUSES, weights=[0.4, 0.3, 0.3])[0]
        name = f"{random.choice(WORDS)}-{i:06d}"
        assignee = random.choice(ASSIGNEES)
        content = f"{name}：请{assignee}在截止时间前完成相关材料准备与线下确认。"
        rows.append((
            name, assignee, content,
            deadline.strftime("%Y-%m-%d %H:%M"),
            remind.strftime("%Y-%m-%d %H:%M"),
            status, "",
            1 if status == "已完成" else 0,
            now.strftime("%Y-%m-%d %H:%M"),
            created.strftime("%Y-%m-%d %H:%M"),
            created.strftime("%Y-%m-%d %H:%M"),
        ))

    conn.executemany(
        "INSERT INTO tasks(name, assignee, content, deadline, reminder_time, status, notes,"
        " triggered, status_changed_at, created_at, updated_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    print(f"seeded {count} tasks into {db.db_path()}")

    # quick benchmark
    t0 = datetime.now()
    repository.list_tasks(page=1, page_size=200)
    t1 = datetime.now()
    repository.list_tasks(page=1, page_size=200, criteria={"keyword": "报表"})
    t2 = datetime.now()
    repository.list_tasks(page=1, page_size=200, sort_key="deadline", sort_dir="asc")
    t3 = datetime.now()
    print(f"list_tasks page1(200): {(t1 - t0).total_seconds() * 1000:.1f} ms")
    print(f"search keyword page1(200): {(t2 - t1).total_seconds() * 1000:.1f} ms")
    print(f"sort by deadline page1(200): {(t3 - t2).total_seconds() * 1000:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
