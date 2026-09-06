"""全功能 E2E 走查：无头环境（QT_QPA_PLATFORM=offscreen）逐模块验证核心用户流程。

运行：python scripts/walkthrough.py
覆盖：CRUD / 校验 / 排序循环 / 分页回退 / 列配置持久化 / 搜索与保存的搜索 /
      导入导出 / 备份恢复 / 提醒触发与弹窗队列 / 历史 / 看板 / 设置信号联动 / 主题
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from task_reminder import db, repository as repo  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, extra: str = ""):
    (PASS if cond else FAIL).append(name)
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  -- {extra}" if extra and not cond else ""))


def main() -> int:
    app = QApplication(sys.argv)

    # ---- 临时数据库，避免碰真实 %APPDATA% ----
    tmp = Path(tempfile.mkdtemp(prefix="tr_walkthrough_"))
    db.init(str(tmp / "tasks.db"))

    # ================= 数据层 =================
    print("\n===== 数据层：CRUD / 校验 =====")
    tid = repo.add_task("写报告", "张三", "<b>季度</b>报告", "2026-09-10 12:00", "2026-09-10 09:00")
    check("新增任务", tid > 0)
    t = repo.get_task(tid)
    check("富文本内容保存", t.content == "<b>季度</b>报告")
    check("摘要取名称", t.summary().startswith("写报告"))
    try:
        repo.add_task("", "张三", "", "2026-09-10 12:00", "2026-09-10 09:00")
        check("空名称被拒绝", False)
    except repo.ValidationError:
        check("空名称被拒绝", True)
    try:
        repo.add_task("x", "y", "", "2026-09-10 12:00", "2026-09-10 13:00")
        check("提醒晚于截止被拒绝", False)
    except repo.ValidationError:
        check("提醒晚于截止被拒绝", True)

    # 状态流转与重新提醒（#11）
    repo.set_status(tid, "已完成")
    check("完成后 triggered=1", repo.get_task(tid).triggered == 1)
    future = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    future_dl = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    kwargs = repo._task_kwargs(repo.get_task(tid))
    kwargs.update(status="进行中", reminder_time=future, deadline=future_dl)
    repo.update_task(tid, **kwargs)
    check("已完成→进行中且提醒在未来时重新触发", repo.get_task(tid).triggered == 0)
    repo.set_status(tid, "已完成")
    repo.set_status(tid, "进行中")   # 提醒时间仍在未来 → 应重新允许
    check("再次改回未完成仍重新触发", repo.get_task(tid).triggered == 0)

    # ================= 提醒触发 =================
    print("\n===== 提醒服务与弹窗队列 =====")
    past = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
    due_id = repo.add_task("到期任务", "李四", "内容", (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), past)
    due = repo.due_for_reminder()
    check("到期任务被查出", any(x.id == due_id for x in due))
    hid = repo.mark_triggered(due_id)
    check("mark_triggered 返回历史 id", hid and hid > 0)
    check("triggered 置位", repo.get_task(due_id).triggered == 1)
    logs, total = repo.list_history(1, 50, "", "")
    check("提醒历史已记录", total >= 1)

    from task_reminder.notifier import Notifier
    notifier = Notifier()
    fired = []
    notifier.responded.connect(fired.append)
    t_due = repo.get_task(due_id)
    notifier.notify(t_due, hid)
    notifier.notify(t_due, hid)      # 两条入队
    notifier.pump()
    app.processEvents()
    check("弹窗弹出且持有队列", notifier._dialog is not None and notifier.pending_count() == 2)
    notifier._dialog._respond("close")       # 关闭第一个
    app.processEvents()
    check("关闭后立即弹出队列中下一条（#2 修复）", notifier._dialog is not None)
    notifier._dialog._respond("done")        # 标记完成
    app.processEvents()
    check("响应回调收到 done", fired == ["close", "done"])
    check("队列清空", notifier.pending_count() == 0)
    check("标记完成同步状态", repo.get_task(due_id).status == "已完成")

    # 稍后提醒
    snooze_id = repo.add_task("稍后提醒", "王五", "", (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), past)
    repo.mark_triggered(snooze_id)
    notifier.notify(repo.get_task(snooze_id), 0)
    notifier.pump()
    app.processEvents()
    notifier._dialog._respond("snooze")
    app.processEvents()
    st = repo.get_task(snooze_id)
    check("稍后提醒顺延且重新触发", st.triggered == 0 and
          datetime.strptime(st.reminder_time, "%Y-%m-%d %H:%M") > datetime.now() + timedelta(minutes=4))

    # ================= UI：任务页 =================
    print("\n===== 任务页：排序 / 分页 / 列配置 =====")
    from task_reminder.ui.tasks_page import TasksPage
    page = TasksPage()
    page.show()
    app.processEvents()
    for i in range(5):
        repo.add_task(f"任务{i:02d}", f"同学{i%2}", "", "2026-09-15 12:00",
                      (datetime.now() + timedelta(days=i + 1)).strftime("%Y-%m-%d %H:%M"))
    page.refresh()
    check("刷新加载数据", page.model.rowCount() == 8, f"实际 {page.model.rowCount()}")
    check("分页信息", "共 8 条" in page.pager.lbl_info.text())

    # 排序循环 asc → desc → 默认
    page._on_header_clicked(2)   # 截止时间列
    check("点击一次→升序", (page.sort_key, page.sort_dir) == ("deadline", "asc"))
    page._on_header_clicked(2)
    check("再点→降序", (page.sort_key, page.sort_dir) == ("deadline", "desc"))
    page._on_header_clicked(2)
    check("三击→默认", page.sort_key == "created_at" and page.sort_dir == "")

    # 分页回退：跳到超出页码后刷新
    page.page_no = 9
    page.refresh()
    check("超页自动回退（# 已有修复）", page.page_no == 1)

    # 列配置：拖拽 + 持久化 + 新实例恢复（#4）
    header = page.view.horizontalHeader()
    header.moveSection(0, 3)     # 把名称列拖到第 4 位
    app.processEvents()
    saved = page._column_state()
    check("保存顺序反映拖拽", [s["id"] for s in saved][:4] == ["assignee", "deadline", "reminder_time", "name"])
    page._save_states()
    page2 = TasksPage()
    check("新实例恢复拖拽后的列顺序", page2.model.column_ids[:4] == ["assignee", "deadline", "reminder_time", "name"])
    page2._reset_columns()
    check("重置列配置", page2.model.column_ids[0] == "name")

    # 每页条数同步（#5）
    page.pager._set_size(50)
    check("分页菜单写回配置", repo and int(db.get_conn().execute(
        "SELECT value FROM user_settings WHERE key='page_size'").fetchone()[0]) == 50)

    # ================= 搜索栏 =================
    print("\n===== 搜索：关键词 / 条件 / 保存的搜索 =====")
    sb = page.search
    sb.edit_keyword.setText("报告")
    sb._emit()
    app.processEvents()
    page.refresh()
    check("关键词过滤", page.model.rowCount() == 1)
    sb.reset()
    sb._debounce.stop()
    page.refresh()
    check("重置恢复全部", page.model.rowCount() == 8, f"实际 {page.model.rowCount()}")
    sb.edit_assignee.setText("同学0")
    sb._emit()
    page.refresh()
    check("执行人精确过滤", page.model.rowCount() == 3)
    sb.reset()
    sb._debounce.stop()

    repo.save_search("我的搜索", {"keyword": "任务"})
    sb.reload_saved_searches()
    check("保存的搜索进入下拉框", sb.cmb_saved.count() == 1)
    sb._load_saved()
    check("加载搜索自动展开高级面板（#7）", sb.btn_advanced.isChecked())
    check("加载后条件生效", sb.criteria().get("keyword") == "任务")
    check("重置按钮存在（#8）", hasattr(sb, "btn_reset") and sb.btn_reset.text() == "重置")

    # ================= 任务对话框 =================
    print("\n===== 任务对话框默认时间 =====")
    from task_reminder.ui.task_dialog import TaskDialog
    dlg = TaskDialog()
    check("默认提醒<截止（任意时刻，#3）", dlg.dt_reminder.dateTime() < dlg.dt_deadline.dateTime())
    dlg.edit_name.setText("测试任务")
    dlg.edit_assignee.setText("测试人")
    check("填名后初始校验通过", dlg._validate() is None, dlg.lbl_error.text())
    dlg.close()

    # ================= 导入导出 =================
    print("\n===== Excel 导入导出 / 备份恢复 =====")
    from task_reminder import excel_io
    xlsx = str(tmp / "export.xlsx")
    n = excel_io.export_tasks(xlsx, repo.all_tasks())
    check("导出任务", n == 8, f"实际 {n}")
    rows = excel_io.read_rows(xlsx)
    check("读回行数一致", len(rows) == 8, f"实际 {len(rows)}")
    # 删光后导入（skip 策略无重复 → 全部新增）
    repo.delete_tasks([x.id for x in repo.all_tasks()])
    report = excel_io.import_tasks(xlsx, strategy="skip")
    check("导入新增", report.added == 8 and len(report.errors) == 0, report.summary())
    report2 = excel_io.import_tasks(xlsx, strategy="skip")
    check("重复导入被跳过", report2.skipped == 8)

    from task_reminder import backup
    bjson = str(tmp / "backup.json")
    check("备份导出", backup.export_json(bjson) == 8)
    repo.delete_tasks([x.id for x in repo.all_tasks()])
    n_t, n_h = backup.import_json(bjson)
    check("备份恢复", n_t == 8 and repo.stats()["total"] == 8)

    # ================= 主窗口集成 =================
    print("\n===== 主窗口：设置信号联动 / 页面切换 =====")
    from task_reminder.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()

    # 设置页改轮询间隔 → 立即生效（#1）
    win.settings_page.spin_interval.setValue(9)
    check("轮询间隔立即生效", win.service._timer.interval() == 9000)
    win.settings_page.cmb_page_size.setCurrentIndex(3)   # 500
    check("每页条数立即生效", win.tasks_page.pager.size == 500)
    check("设置页下拉框与任务页双向同步", win.settings_page.cmb_page_size.currentData() == 500)
    win.tasks_page.pager._set_size(100)                  # 任务页反向改
    check("任务页改后设置页同步（#5）", win.settings_page.cmb_page_size.currentData() == 100)

    # 已保存搜索删除同步（#6）
    win._switch_page(3)   # 设置页 → reload_searches
    win.settings_page.list_searches.setCurrentRow(0)
    win.settings_page._del_search()
    check("设置页删除搜索后任务页同步", win.tasks_page.search.cmb_saved.count() == 0)

    # 恢复备份 → 各页刷新（#1）
    n2 = repo.add_task("恢复测试", "赵六", "", "2026-09-20 12:00", "2026-09-20 09:00")
    win.settings_page.data_restored.emit()
    check("恢复后任务页刷新", win.tasks_page.model.rowCount() >= 1)

    # 看板与历史页
    win._switch_page(1)
    check("看板统计", win.dashboard_page.card_total.lbl_value.text() == str(repo.stats()["total"]))
    win._switch_page(2)
    check("历史页加载", "共" in win.history_page.lbl_info.text())
    win.history_page._turn(5)
    check("历史翻页有上界（#9）", win.history_page.page_no == 1)

    # 主题切换
    win.settings_page.cmb_theme.setCurrentIndex(1)
    check("深色主题应用", "0F172A" in QApplication.instance().styleSheet())

    # 提醒全链路：service.tick → task_due → notifier
    past2 = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
    rid = repo.add_task("链路任务", "孙七", "", "2026-09-21 12:00", past2)
    win.service.tick()
    app.processEvents()
    check("tick 触发入队/弹窗", repo.get_task(rid).triggered == 1)
    if win.notifier._dialog is not None:
        win.notifier._dialog._respond("close")
        app.processEvents()

    # 清理
    repo.delete_tasks([x.id for x in repo.all_tasks()])
    win.service.stop()
    win.close()
    print(f"\n========== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ==========")
    if FAIL:
        print("失败项：", "; ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
