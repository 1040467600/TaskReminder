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

from PyQt6.QtCore import QDate, Qt, QTimer  # noqa: E402
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
    tid = repo.add_task("写报告", "张三", "<b>季度</b>报告", "2026-09-10 12:00", "2026-09-10 09:00",
                        category="案件办理")
    check("新增任务", tid > 0)
    t = repo.get_task(tid)
    check("富文本内容保存", t.content == "<b>季度</b>报告")
    check("摘要取名称", t.summary().startswith("写报告"))
    check("任务类别保存", t.category == "案件办理", f"实际 {t.category!r}")
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

    # busy_timeout（v2.4.1 并发健壮性）
    check("busy_timeout >= 3000",
          db.get_conn().execute("PRAGMA busy_timeout").fetchone()[0] >= 3000)
    # 双空时间允许 / 单空拒绝（v2.4.1）
    _et_id = repo.add_task("无时间任务", "张三", "", "", "")
    check("双空时间允许保存", repo.get_task(_et_id) is not None)
    try:
        repo.validate_task("单空", "张三", "", "2026-09-10 12:00", "")
        check("单空时间被拒绝", False)
    except repo.ValidationError:
        check("单空时间被拒绝", True)
    check("空提醒不参与到期查询", not any(x.id == _et_id for x in repo.due_for_reminder()))
    # 删除任务保留提醒历史（v2.4.1）
    _hist_id = repo.add_task("历史保留", "张三", "",
                             "2026-09-10 12:00", "2026-09-10 09:00")
    repo.mark_triggered(_hist_id)
    _h_before = repo.list_history(1, 200, "", "")[1]
    repo.delete_task(_hist_id)
    check("删除任务保留提醒历史", repo.list_history(1, 200, "", "")[1] == _h_before)
    repo.delete_task(_et_id)

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

    # Esc/× 关闭（rejected）不卡死队列（v2.4.1）
    rj1 = repo.add_task("Esc任务甲", "李四", "",
                        (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), past)
    rj2 = repo.add_task("Esc任务乙", "李四", "",
                        (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), past)
    h1 = repo.mark_triggered(rj1)
    h2 = repo.mark_triggered(rj2)
    notifier.notify(repo.get_task(rj1), h1)
    notifier.notify(repo.get_task(rj2), h2)
    notifier.pump()
    app.processEvents()
    dlg_first = notifier._dialog
    dlg_first.reject()                       # 模拟 Esc / 标题栏 ×
    app.processEvents()
    resp_close = db.get_conn().execute(
        "SELECT response FROM reminder_history WHERE id=?", (h1,)).fetchone()[0]
    check("Esc 关闭历史记 close", resp_close == "close")
    check("Esc 后队列不卡死（自动弹下一条）",
          notifier._dialog is not None and notifier._dialog is not dlg_first)
    notifier._dialog.reject()
    app.processEvents()
    check("Esc 全部关闭后队列清空", notifier._dialog is None and notifier.pending_count() == 0)
    # 弹窗任务已被删除时点"标记完成"不崩（v2.4.1）
    del_id = repo.add_task("弹窗中删除", "李四", "",
                           (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), past)
    del_hid = repo.mark_triggered(del_id)
    from task_reminder.notifier import ReminderDialog as _RDlg
    _dlg = _RDlg(repo.get_task(del_id), del_hid)
    repo.delete_task(del_id)
    _dlg._respond("done")
    check("弹窗任务被删后响应不崩溃", repo.get_task(del_id) is None)

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
        # 截止统一取 30 天后，保证提醒（未来 1~5 天）始终早于截止，避免硬编码日期失效
        repo.add_task(f"任务{i:02d}", f"同学{i%2}", "",
                      (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M"),
                      (datetime.now() + timedelta(days=i + 1)).strftime("%Y-%m-%d %H:%M"))
    page.refresh()
    _n_all = len(repo.all_tasks())
    check("刷新加载数据", page.model.rowCount() == _n_all, f"实际 {page.model.rowCount()}")
    check("分页信息", f"共 {_n_all} 条" in page.pager.lbl_info.text())

    # 排序循环 asc → desc → 默认
    dl = page.model.column_ids.index("deadline")
    page._on_header_clicked(dl)   # 截止时间列
    check("点击一次→升序", (page.sort_key, page.sort_dir) == ("deadline", "asc"))
    page._on_header_clicked(dl)
    check("再点→降序", (page.sort_key, page.sort_dir) == ("deadline", "desc"))
    page._on_header_clicked(dl)
    check("三击→默认", page.sort_key == "created_at" and page.sort_dir == "")

    # 分页回退：跳到超出页码后刷新
    page.page_no = 9
    page.refresh()
    check("超页自动回退（# 已有修复）", page.page_no == 1)

    # 列配置：拖拽 + 持久化 + 新实例恢复（#4）
    # v2.4 起默认视觉顺序：category, name, content, assignee, deadline, …
    # 把类别列（视觉 0）拖到视觉 3 → name, content, assignee, category, …
    header = page.view.horizontalHeader()
    header.moveSection(0, 3)     # 把类别列拖到第 4 位
    app.processEvents()
    saved = page._column_state()
    check("保存顺序反映拖拽", [s["id"] for s in saved][:4] == ["name", "content", "assignee", "category"])
    page._save_states()
    page2 = TasksPage()
    check("新实例恢复拖拽后的列顺序",
          page2.model.column_ids[:4] == ["name", "content", "assignee", "category"])
    page2._reset_columns()
    check("重置列配置", page2.model.column_ids[0] == "category")
    check("任务类别列在任务名称之前",
          page2.model.column_ids.index("category") < page2.model.column_ids.index("name"))
    check("任务类别列默认显示", "category" in page2.model.column_ids
          and not page2.view.horizontalHeader().isSectionHidden(
              page2.model.column_ids.index("category")))
    # 所有列均为 Interactive（每个边界都可手动调整）
    from PyQt6.QtWidgets import QHeaderView as _QHV
    check("全部列宽可手动调整",
          all(page2.view.horizontalHeader().sectionResizeMode(i)
              == _QHV.ResizeMode.Interactive for i in range(len(page2.model.column_ids))))

    # 每页条数同步（#5）
    page.pager._set_size(50)
    check("分页菜单写回配置", repo and int(db.get_conn().execute(
        "SELECT value FROM user_settings WHERE key='page_size'").fetchone()[0]) == 50)

    # ================= 搜索栏 =================
    print("\n===== 搜索：名称/内容分离 / 日期开关 / 状态防呆 =====")
    sb = page.search
    sb.edit_keyword.setText("报告")
    sb._emit()
    app.processEvents()
    page.refresh()
    check("名称关键词过滤", page.model.rowCount() == 1)
    sb.reset()
    sb._debounce.stop()
    page.refresh()
    check("重置恢复全部", page.model.rowCount() == _n_all, f"实际 {page.model.rowCount()}")
    sb.edit_assignee.setText("同学0")
    sb._emit()
    page.refresh()
    check("执行人精确过滤", page.model.rowCount() == 3)
    sb.reset()
    sb._debounce.stop()

    # 任务类别筛选（v2.3）
    sb.btn_advanced.setChecked(True)
    sb.cmb_category.setCurrentText("案件办理")   # 仅"写报告"是案件办理
    page.refresh()
    check("任务类别筛选", page.model.rowCount() == 1, f"实际 {page.model.rowCount()}")
    check("类别筛选进入条件", sb.criteria().get("category") == "案件办理")
    sb.cmb_category.setCurrentIndex(0)
    sb.reset()
    sb._debounce.stop()
    page.refresh()

    # 名称/内容关键词分开（#1）
    sb.edit_content_kw.setText("季度报告不存在的内容")
    sb._emit()
    page.refresh()
    check("内容关键词独立过滤", page.model.rowCount() == 0)
    check("筛选无结果提示区分（#）", "搜索条件" in page.empty_hint.text())
    sb.reset()
    sb._debounce.stop()
    check("重置按钮存在（#8）", hasattr(sb, "btn_reset") and sb.btn_reset.text() == "重置")
    check("常用搜索已移除（#5）", not hasattr(sb, "cmb_saved") and not hasattr(sb, "btn_load"))

    # 状态全取消自动勾回（防呆）
    for cb in sb.chk_status.values():
        cb.setChecked(False)
    check("状态全取消自动勾回", all(cb.isChecked() for cb in sb.chk_status.values()))
    app.processEvents()

    # 日期范围：日期始终可编辑，复选框限定生效/取消=不限（#4）
    rng = sb._date_ranges["deadline"]
    check("日期默认可编辑", rng["lo"].isEnabled())
    check("日期默认不限", "deadline_from" not in sb.criteria())
    rng["chk"].setChecked(True)
    rng["lo"].setDate(QDate(datetime.now().year + 1, 1, 1))
    check("限定后日期生效", sb.criteria().get("deadline_from", "").startswith(str(datetime.now().year + 1)))
    rng["chk"].setChecked(False)
    check("取消限定恢复不限（#4）", "deadline_from" not in sb.criteria())
    check("取消限定后日期仍可编辑", rng["lo"].isEnabled())

    # 提醒时间范围（v2.4.1）
    check("高级搜索有提醒时间范围", "reminder" in sb._date_ranges)
    rr = sb._date_ranges["reminder"]
    rr["chk"].setChecked(True)
    check("提醒范围生效", "reminder_from" in sb.criteria() and "reminder_to" in sb.criteria())
    rr["chk"].setChecked(False)
    check("提醒范围可取消", "reminder_from" not in sb.criteria())

    # 收起高级面板时显示生效条件徽章（#）
    sb.edit_assignee.setText("张三")
    sb._debounce.stop()
    sb.btn_advanced.setChecked(True)    # 先展开再收起，触发徽章刷新
    app.processEvents()
    sb.btn_advanced.setChecked(False)
    check("收起显示筛选徽章", sb.btn_active.isVisibleTo(sb) and "1 项筛选" in sb.btn_active.text(),
          f"visible={sb.btn_active.isVisibleTo(sb)} text={sb.btn_active.text()!r}")
    sb.reset()
    sb._debounce.stop()
    check("重置后徽章消失", not sb.btn_active.isVisibleTo(sb))

    # 内容列默认可见（#2）
    check("内容列存在且默认显示", "content" in page.model.column_ids)

    # ================= 任务对话框 =================
    print("\n===== 任务对话框默认时间 =====")
    from task_reminder.ui.task_dialog import TaskDialog
    dlg = TaskDialog()
    check("默认提醒<截止（任意时刻，#3）", dlg.dt_reminder.dateTime() < dlg.dt_deadline.dateTime())
    check("新建类别默认其他（v2.4.1）", dlg.cmb_category.currentText() == "其他")
    dlg.edit_name.setText("测试任务")
    dlg.edit_assignee.setText("测试人")
    check("填名后初始校验通过", dlg._validate() is None, dlg.lbl_error.text())
    dlg.cmb_category.setCurrentText("场所检查")
    check("对话框类别可选", dlg.cmb_category.currentText() == "场所检查")
    # 时间可留空（v2.4.1）
    dlg.chk_no_deadline.setChecked(True)
    check("只勾一个时间'无'不能保存", not dlg.btn_ok.isEnabled())
    dlg.chk_no_reminder.setChecked(True)
    check("双'无'可保存且时间框禁用", dlg.btn_ok.isEnabled()
          and not dlg.dt_deadline.isEnabled() and not dlg.dt_reminder.isEnabled())
    dlg._on_save()
    check("无时间任务保存成功", dlg.result() == 1)
    _no_time = [x for x in repo.all_tasks() if x.name == "测试任务"][0]
    check("保存后时间为空", _no_time.deadline == "" and _no_time.reminder_time == "")
    check("空提醒不参与到期查询", not any(x.id == _no_time.id for x in repo.due_for_reminder()))
    dlg2 = TaskDialog(editing_task=_no_time)
    check("编辑空时间任务自动勾'无'",
          dlg2.chk_no_deadline.isChecked() and dlg2.chk_no_reminder.isChecked())
    dlg2.close()
    # 截止=提醒同刻允许（v2.4.1）
    same = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    _same_id = repo.add_task("同刻时间", "测试人", "", same, same)
    check("截止=提醒同刻允许保存", repo.get_task(_same_id) is not None)
    dlg.close()

    # ================= 导入导出 =================
    print("\n===== Excel 导入导出 / 备份恢复 =====")
    from task_reminder import excel_io
    xlsx = str(tmp / "export.xlsx")
    _n_export = len(repo.all_tasks())
    n = excel_io.export_tasks(xlsx, repo.all_tasks())
    check("导出任务", n == _n_export, f"实际 {n}")
    rows = excel_io.read_rows(xlsx)
    check("读回行数一致", len(rows) == _n_export, f"实际 {len(rows)}")
    # 空列表也能导出仅表头文件（v2.4.1）
    xlsx_empty = str(tmp / "empty.xlsx")
    check("空库导出仅表头文件", excel_io.export_tasks(xlsx_empty, []) == 0
          and excel_io.read_rows(xlsx_empty) == [])
    # 删光后导入（skip 策略无重复 → 全部新增）
    repo.delete_tasks([x.id for x in repo.all_tasks()])
    report = excel_io.import_tasks(xlsx, strategy="skip")
    check("导入新增", report.added == _n_export and len(report.errors) == 0, report.summary())
    report2 = excel_io.import_tasks(xlsx, strategy="skip")
    check("重复导入被跳过", report2.skipped == _n_export)

    # 损坏 xlsx 导入抛异常（供 UI 层捕获后友好提示，v2.4.1）
    import openpyxl
    bad_xlsx = str(tmp / "bad.xlsx")
    with open(bad_xlsx, "w", encoding="utf-8") as f:
        f.write("not a real xlsx")
    try:
        excel_io.import_tasks(bad_xlsx)
        check("损坏 xlsx 抛异常", False)
    except Exception:
        check("损坏 xlsx 抛异常", True)

    from task_reminder import backup
    bjson = str(tmp / "backup.json")
    check("备份导出", backup.export_json(bjson) == _n_export)
    repo.delete_tasks([x.id for x in repo.all_tasks()])
    n_t, n_h = backup.import_json(bjson)
    check("备份恢复", n_t == _n_export and repo.stats()["total"] == _n_export)

    # 字段缺失的备份文件可恢复（v2.4.1）
    import json as _json
    minimal = str(tmp / "minimal.json")
    with open(minimal, "w", encoding="utf-8") as f:
        _json.dump({"format": "task_reminder_backup", "version": 1,
                    "tasks": [{"id": 8888, "name": "极简", "assignee": "钱七"}],
                    "history": []}, f, ensure_ascii=False)
    mt, mh = backup.import_json(minimal)
    check("缺字段备份可恢复", mt == 1 and repo.get_task(8888).status == "未开始")

    # ================= 主窗口集成 =================
    print("\n===== 主窗口：设置信号联动 / 页面切换 =====")
    from task_reminder.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    app.processEvents()

    # 记忆位置在屏幕外时回到主屏（v2.4.1）
    from task_reminder import app_config as _acfg
    from PyQt6.QtGui import QGuiApplication as _QGA
    _acfg.set("window_state", {"x": -99999, "y": -99999, "w": 1000, "h": 700,
                               "maximized": False})
    win_off = MainWindow()
    app.processEvents()
    check("屏幕外记忆位置回到主屏",
          _QGA.primaryScreen().availableGeometry().intersects(win_off.frameGeometry()))
    win_off.service.stop()
    win_off.hide()

    # 进入界面 / 品牌标题（v2.4）
    from task_reminder.ui.welcome import WelcomeWindow
    from PyQt6.QtWidgets import QLabel as _QLabel
    welcome = WelcomeWindow()
    _fired = []
    welcome.entered.connect(lambda: _fired.append(1))
    welcome.btn_enter.click()
    check("进入按钮发出进入信号", _fired == [1])
    check("欢迎页显示系统全称",
          welcome.findChild(_QLabel, "welcomeTitle1").text() == "彭城派出所"
          and welcome.findChild(_QLabel, "welcomeTitle2").text() == "任务闭环管理系统")
    check("侧边栏仅品牌标题（无铃铛）",
          win.findChild(_QLabel, "appBrand1") is not None
          and win.findChild(_QLabel, "appTitle") is None)
    welcome.close()

    # 设置页改轮询间隔 → 立即生效（#1）
    win.settings_page.spin_interval.setValue(9)
    check("轮询间隔立即生效", win.service._timer.interval() == 9000)
    win.settings_page.cmb_page_size.setCurrentIndex(3)   # 500
    check("每页条数立即生效", win.tasks_page.pager.size == 500)
    check("设置页下拉框与任务页双向同步", win.settings_page.cmb_page_size.currentData() == 500)
    win.tasks_page.pager._set_size(100)                  # 任务页反向改
    check("任务页改后设置页同步（#5）", win.settings_page.cmb_page_size.currentData() == 100)

    # 已保存搜索功能已移除（#5）：设置页不应再有管理控件
    win._switch_page(3)
    check("设置页无已保存搜索管理区", not hasattr(win.settings_page, "list_searches"))
    check("搜索栏无常用搜索控件", not hasattr(win.tasks_page.search, "cmb_saved"))

    # 恢复备份 → 各页刷新（#1）
    n2 = repo.add_task("恢复测试", "赵六", "", "2026-09-20 12:00", "2026-09-20 09:00")
    win.settings_page.data_restored.emit()
    check("恢复后任务页刷新", win.tasks_page.model.rowCount() >= 1)

    # 看板与历史页
    win._switch_page(1)
    check("看板统计", win.dashboard_page.card_total.lbl_value.text() == str(repo.stats()["total"]))
    # 看板卡片点击 → 跳任务页并应用筛选（#）
    win.dashboard_page.card_overdue.clicked.emit("overdue")
    app.processEvents()
    check("卡片点击跳任务页", win.stack.currentIndex() == 0)
    c = win.tasks_page.search.criteria()
    check("卡片筛选已应用", "deadline_to" in c and c.get("statuses") == ["未开始", "进行中"])
    win.tasks_page.search.reset()
    win.tasks_page.search._debounce.stop()
    win._switch_page(2)
    check("历史页加载", "共" in win.history_page.lbl_info.text())
    win.history_page._turn(5)
    check("历史翻页有上界（#9）", win.history_page.page_no == 1)

    # 主题切换
    win.settings_page.cmb_theme.setCurrentIndex(1)
    check("深色主题应用", "0F172A" in QApplication.instance().styleSheet())

    # 提醒全链路：service.tick → task_due_batch → notifier
    past2 = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
    dl2 = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
    rid = repo.add_task("链路任务", "孙七", "", dl2, past2)
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
