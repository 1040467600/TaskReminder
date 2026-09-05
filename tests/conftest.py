"""测试夹具：每个用例使用独立的临时数据库。"""
from __future__ import annotations

import pytest

from task_reminder import db


@pytest.fixture(autouse=True)
def db_conn(tmp_path):
    path = str(tmp_path / "test_tasks.db")
    conn = db.init(path)
    yield conn
    db.close()
