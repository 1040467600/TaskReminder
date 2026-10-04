"""v2.3.0 任务类别：CRUD / 迁移 / 筛选 / 对话框 / 搜索 / 备份 / Excel / 表格模型。"""
from __future__ import annotations

import json
import sqlite3

import pytest
from openpyxl import Workbook

from task_reminder import backup, db, excel_io, repository as repo
from task_reminder.models import TaskCategory, normalize_category

DL = "2030-01-01 12:00"
RM = "2030-01-01 09:00"


def mk(name="类别任务", category=None, **kw):
    if category is not None:
        kw["category"] = category
    return repo.add_task(name, "张三", "内容", DL, RM, **kw)


# ---------------------------------------------------------------------------
# 数据层
class TestCategoryCrud:
    def test_default_category(self):
        tid = mk()
        assert repo.get_task(tid).category == TaskCategory.OTHER

    def test_all_categories_roundtrip(self):
        for i, c in enumerate(TaskCategory.ALL):
            tid = mk(name=f"任务{i}", category=c)
            assert repo.get_task(tid).category == c

    def test_invalid_category_normalized(self):
        tid = mk(category="不存在的类别")
        assert repo.get_task(tid).category == TaskCategory.OTHER

    def test_empty_category_normalized(self):
        tid = mk(category="")
        assert repo.get_task(tid).category == TaskCategory.OTHER

    def test_update_category(self):
        tid = mk(category="案件办理")
        t = repo.get_task(tid)
        repo.update_task(tid, name=t.name, assignee=t.assignee, content=t.content,
                         deadline=t.deadline, reminder_time=t.reminder_time,
                         status=t.status, notes=t.notes, category="反诈宣传")
        assert repo.get_task(tid).category == "反诈宣传"

    def test_set_status_preserves_category(self):
        tid = mk(category="噪音处置")
        repo.set_status(tid, "进行中")
        assert repo.get_task(tid).category == "噪音处置"

    def test_normalize_category_helper(self):
        assert normalize_category("案件办理") == "案件办理"
        assert normalize_category("xxx") == TaskCategory.OTHER
        assert normalize_category("") == TaskCategory.OTHER


class TestCategoryQuery:
    def test_filter_by_category(self):
        a = mk(name="甲", category="案件办理")
        b = mk(name="乙", category="反诈宣传")
        c = mk(name="丙")   # 其他
        tasks, total = repo.list_tasks(criteria={"category": "案件办理"})
        assert total == 1 and tasks[0].id == a
        tasks, total = repo.list_tasks(criteria={"category": "其他"})
        assert total == 1 and tasks[0].id == c
        # 不带类别条件 → 全部
        _, total = repo.list_tasks()
        assert total == 3

    def test_filter_combined_with_status(self):
        a = mk(name="甲", category="案件办理")
        mk(name="乙", category="案件办理")
        repo.set_status(a, "已完成")
        _, total = repo.list_tasks(criteria={"category": "案件办理", "statuses": ["未开始"]})
        assert total == 1

    def test_sort_by_category(self):
        mk(name="甲", category="反诈宣传")
        mk(name="乙", category="案件办理")
        tasks, _ = repo.list_tasks(sort_key="category", sort_dir="asc")
        # SQLite 按二进制（码点）序比较中文：反(U+53CD) < 案(U+6848)
        assert [t.category for t in tasks] == sorted(["反诈宣传", "案件办理"])


# ---------------------------------------------------------------------------
# 旧库迁移
class TestMigration:
    def test_old_db_without_category_column(self, tmp_path):
        """v2.2 旧库（无 category 列）打开后自动补列，存量数据默认"其他"。"""
        old_path = str(tmp_path / "old.db")
        conn = sqlite3.connect(old_path)
        conn.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                assignee TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                content_plain TEXT NOT NULL DEFAULT '',
                deadline TEXT NOT NULL DEFAULT '',
                reminder_time TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '未开始',
                notes TEXT NOT NULL DEFAULT '',
                triggered INTEGER NOT NULL DEFAULT 0,
                status_changed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.execute(
            "INSERT INTO tasks(name, assignee, content, deadline, reminder_time)"
            " VALUES('旧任务', '李四', '', '2030-01-01 12:00', '2030-01-01 09:00')")
        conn.commit()
        conn.close()

        conn = db.init(old_path)   # 触发迁移
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        assert "category" in cols
        row = conn.execute("SELECT name, category FROM tasks").fetchone()
        assert row["name"] == "旧任务" and row["category"] == "其他"
        # 迁移后的库可正常写入带类别的任务
        tid = mk(category="场所检查")
        assert repo.get_task(tid).category == "场所检查"
        db.close()

    def test_fresh_db_has_category(self):
        cols = {r[1] for r in db.get_conn().execute("PRAGMA table_info(tasks)")}
        assert "category" in cols


# ---------------------------------------------------------------------------
# UI
class TestCategoryUi:
    def test_category_column_before_name(self, qtbot):
        """v2.4：任务类别列默认位于任务名称之前。"""
        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        ids = page.model.column_ids
        assert ids[0] == "category"
        assert ids.index("category") < ids.index("name")

    def test_legacy_column_state_moves_category_ahead_of_name(self, qtbot):
        """v2.3 持久化的旧列序（类别在名称之后）加载后自动迁移到名称之前。"""
        import json

        from task_reminder import app_config
        from task_reminder.ui.tasks_page import TasksPage
        old_state = [
            {"id": "name", "visible": True, "width": 220},
            {"id": "content", "visible": True, "width": 280},
            {"id": "assignee", "visible": True, "width": 100},
            {"id": "deadline", "visible": True, "width": 150},
            {"id": "reminder_time", "visible": True, "width": 150},
            {"id": "status", "visible": True, "width": 96},
            {"id": "notes", "visible": False, "width": 180},
            {"id": "actions", "visible": True, "width": 132},
            {"id": "category", "visible": True, "width": 110},
        ]
        app_config.set("column_state", json.dumps(old_state, ensure_ascii=False))
        page = TasksPage()
        qtbot.addWidget(page)
        ids = page.model.column_ids
        assert ids.index("category") == ids.index("name") - 1

    def test_all_columns_interactive_and_widths_independent(self, qtbot):
        """回归：拖动执行人边界只改执行人列，不再误改任务名称列。"""
        from PyQt6.QtWidgets import QHeaderView

        from task_reminder.ui.tasks_page import TasksPage
        page = TasksPage()
        qtbot.addWidget(page)
        header = page.view.horizontalHeader()
        assert all(header.sectionResizeMode(i) == QHeaderView.ResizeMode.Interactive
                   for i in range(header.count()))
        name_li = page.model.column_ids.index("name")
        assignee_li = page.model.column_ids.index("assignee")
        name_w_before = header.sectionSize(name_li)
        header.resizeSection(assignee_li, header.sectionSize(assignee_li) + 40)
        assert header.sectionSize(name_li) == name_w_before
        assert header.sectionSize(assignee_li) > 100

    def test_task_dialog_save_category(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog()
        qtbot.addWidget(dlg)
        dlg.edit_name.setText("对话框任务")
        dlg.edit_assignee.setText("张三")
        dlg.cmb_category.setCurrentText("矛盾纠纷调处")
        dlg._on_save()
        assert dlg.result() == 1
        t = repo.all_tasks()[0]
        assert t.category == "矛盾纠纷调处"

    def test_task_dialog_load_category(self, qtbot):
        from task_reminder.ui.task_dialog import TaskDialog
        tid = mk(category="重点人员管控")
        dlg = TaskDialog(editing_task=repo.get_task(tid))
        qtbot.addWidget(dlg)
        assert dlg.cmb_category.currentText() == "重点人员管控"
        # 旧数据的非法类别显示为"其他"
        tid2 = mk(name="旧数据")
        db.get_conn().execute("UPDATE tasks SET category='垃圾值' WHERE id=?", (tid2,))
        dlg2 = TaskDialog(editing_task=repo.get_task(tid2))
        qtbot.addWidget(dlg2)
        assert dlg2.cmb_category.currentText() == "其他"

    def test_search_bar_category_criteria(self, qtbot):
        from task_reminder.ui.search_bar import SearchBar
        sb = SearchBar()
        qtbot.addWidget(sb)
        assert "category" not in sb.criteria()          # 默认"全部"不限
        sb.cmb_category.setCurrentText("噪音处置")
        assert sb.criteria()["category"] == "噪音处置"
        assert "category" in sb.adv_keys_in_use()
        sb.set_criteria({"category": "反诈宣传"})
        assert sb.cmb_category.currentText() == "反诈宣传"
        sb.reset()
        assert sb.cmb_category.currentIndex() == 0
        assert "category" not in sb.criteria()

    def test_table_model_category_column(self, qtbot):
        from PyQt6.QtCore import Qt

        from task_reminder.ui.task_table_model import TaskTableModel
        from task_reminder.ui.widgets import COLUMNS
        mk(name="模型任务", category="场所检查")
        m = TaskTableModel()
        m.set_columns([c[0] for c in COLUMNS])
        m.set_tasks(repo.all_tasks())
        idx = m.column_ids.index("category")
        assert m.headerData(idx, Qt.Orientation.Horizontal) == "任务类别"
        assert m.data(m.index(0, idx)) == "场所检查"

    def test_tasks_page_filter_via_search(self, qtbot):
        from task_reminder.ui.tasks_page import TasksPage
        a = mk(name="页面甲", category="反诈宣传")
        mk(name="页面乙", category="案件办理")
        page = TasksPage()
        qtbot.addWidget(page)
        page.search.btn_advanced.setChecked(True)
        page.search.cmb_category.setCurrentText("反诈宣传")
        page.refresh()
        assert page.model.rowCount() == 1
        assert page.model.task_at(0).id == a


# ---------------------------------------------------------------------------
# 备份
class TestCategoryBackup:
    def test_backup_roundtrip_keeps_category(self, tmp_path):
        tid = mk(category="反诈宣传")
        path = str(tmp_path / "b.json")
        assert backup.export_json(path) == 1
        repo.delete_tasks([tid])
        n_t, _ = backup.import_json(path)
        assert n_t == 1
        assert repo.get_task(tid).category == "反诈宣传"

    def test_old_backup_without_category(self, tmp_path):
        """v2.2 旧备份（无 category 键）导入后类别回退"其他"。"""
        payload = {
            "format": "task_reminder_backup",
            "version": 2,
            "exported_at": "2026-01-01 00:00",
            "tasks": [{
                "id": 99, "name": "旧备份任务", "assignee": "王五", "content": "",
                "content_plain": "", "deadline": DL, "reminder_time": RM,
                "status": "未开始", "notes": "", "triggered": 0,
                "status_changed_at": "", "created_at": "", "updated_at": "",
            }],
            "history": [],
        }
        path = str(tmp_path / "old.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        n_t, _ = backup.import_json(path)
        assert n_t == 1
        assert repo.get_task(99).category == "其他"


# ---------------------------------------------------------------------------
# Excel
class TestCategoryExcel:
    def test_export_import_category_roundtrip(self, tmp_path):
        mk(name="甲", category="案件办理")
        mk(name="乙", category="噪音处置")
        mk(name="丙")
        path = str(tmp_path / "e.xlsx")
        assert excel_io.export_tasks(path, repo.all_tasks()) == 3
        rows = excel_io.read_rows(path)
        by_name = {r["name"]: r["category"] for r in rows}
        assert by_name == {"甲": "案件办理", "乙": "噪音处置", "丙": "其他"}
        repo.delete_tasks([t.id for t in repo.all_tasks()])
        report = excel_io.import_tasks(path)
        assert report.added == 3 and not report.errors
        cats = {t.name: t.category for t in repo.all_tasks()}
        assert cats == {"甲": "案件办理", "乙": "噪音处置", "丙": "其他"}

    def test_import_old_format_without_category(self, tmp_path):
        """旧 8 列格式（无任务类别列）导入 → 类别默认"其他"。"""
        wb = Workbook()
        ws = wb.active
        ws.append(["任务名称", "执行人", "任务内容", "截止时间", "提醒时间", "状态", "备注", "创建时间"])
        ws.append(["旧格式任务", "赵六", "x", DL, RM, "未开始", "", ""])
        path = str(tmp_path / "old.xlsx")
        wb.save(path)
        report = excel_io.import_tasks(path)
        assert report.added == 1
        assert repo.all_tasks()[0].category == "其他"

    def test_import_invalid_category_fallback(self, tmp_path):
        wb = Workbook()
        ws = wb.active
        ws.append(excel_io.HEADERS)
        ws.append(["非法类别任务", "钱七", "x", DL, RM, "未开始", "", "", "不存在的类别"])
        path = str(tmp_path / "bad.xlsx")
        wb.save(path)
        report = excel_io.import_tasks(path)
        assert report.added == 1
        assert repo.all_tasks()[0].category == "其他"
