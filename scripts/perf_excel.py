"""Excel 导出性能基准：10 万条任务导出耗时。

用法：python scripts\\perf_excel.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["APPDATA"] = str(ROOT / ".tmp_test" / "perf_100k")

from task_reminder import db, excel_io, repository  # noqa: E402

OUT = ROOT / ".tmp_test" / "perf_100k" / "export_100k.xlsx"
DB = ROOT / ".tmp_test" / "perf_100k" / "tasks.db"


def main() -> int:
    db.init(str(DB))
    t0 = time.perf_counter()
    tasks = repository.all_tasks()
    t1 = time.perf_counter()
    n = excel_io.export_tasks(str(OUT), tasks)
    t2 = time.perf_counter()
    print(f"fetched {n} tasks: {(t1 - t0) * 1000:.0f} ms")
    print(f"exported {n} rows -> {OUT.name}: {(t2 - t1):.1f} s")
    print(f"file size: {OUT.stat().st_size / 1024 / 1024:.1f} MB")
    ok = (t2 - t1) <= 10.0
    print("export <= 10s:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
