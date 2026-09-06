"""Excel 导入导出（openpyxl，纯 Python，免装 Office）。

导出列：任务名称 / 执行人 / 任务内容 / 截止时间 / 提醒时间 / 状态 / 备注 / 创建时间
导入校验：必填、长度（名称 1-50、内容 ≤5000）、时间格式与先后关系；
冲突处理：与现有任务「名称+执行人+截止时间」重复时按策略跳过或覆盖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Task, fmt, html_to_plain, parse

HEADERS = ["任务名称", "执行人", "任务内容", "截止时间", "提醒时间", "状态", "备注", "创建时间"]

WIDTHS = [28, 12, 46, 18, 18, 10, 26, 20]

STATUS_DEFAULT = "未开始"


# ---------------------------------------------------------------------------
# 导出
def export_tasks(path: str, tasks: Iterable[Task], sheet_title: str = "任务列表") -> int:
    """导出任务到 .xlsx，返回行数。

    首选 xlsxwriter constant_memory 流式引擎（10 万条 ≤10 秒），
    未安装时回退 openpyxl write_only 模式。
    """
    tasks = list(tasks)
    count = len(tasks)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        _export_xlsxwriter(path, tasks, sheet_title)
    except ImportError:
        _export_openpyxl(path, tasks, sheet_title)
    return count


def _export_xlsxwriter(path: str, tasks: list[Task], sheet_title: str):
    import xlsxwriter

    wb = xlsxwriter.Workbook(path, {"constant_memory": True,
                                    "default_font_name": "微软雅黑",
                                    "default_font_size": 10})
    ws = wb.add_worksheet(sheet_title[:31])

    head_fmt = wb.add_format({"bold": True, "font_color": "#FFFFFF",
                              "bg_color": "#2F5597", "align": "center",
                              "valign": "vcenter", "border": 0})
    for i, w in enumerate(WIDTHS):
        ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)
    for c, h in enumerate(HEADERS):
        ws.write(0, c, h, head_fmt)

    r = 1
    for t in tasks:
        ws.write_row(r, 0, [
            t.name or t.summary(50),
            t.assignee,
            html_to_plain(t.content),
            t.deadline,
            t.reminder_time,
            t.status,
            t.notes or "",
            t.created_at,
        ])
        r += 1
    ws.write(r + 1, 0, f"导出时间：{fmt(datetime.now())}    共 {len(tasks)} 条    由 任务提醒助手 导出")
    wb.close()


def _export_openpyxl(path: str, tasks: list[Task], sheet_title: str):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=sheet_title[:31])

    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5597")
    header_align = Alignment(horizontal="center", vertical="center")
    header_row = []
    for h in HEADERS:
        c = WriteOnlyCell(ws, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = header_align
        header_row.append(c)
    ws.append(header_row)
    ws.freeze_panes = "A2"

    for t in tasks:
        ws.append([
            t.name or t.summary(50),
            t.assignee,
            html_to_plain(t.content),
            t.deadline,
            t.reminder_time,
            t.status,
            t.notes or "",
            t.created_at,
        ])

    ws.append([])
    ws.append([f"导出时间：{fmt(datetime.now())}    共 {len(tasks)} 条    由 任务提醒助手 导出"])
    wb.save(path)


# ---------------------------------------------------------------------------
# 导入
@dataclass
class ImportReport:
    total: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"共读取 {self.total} 行：新增 {self.added}，覆盖 {self.updated}，"
                 f"跳过 {self.skipped}，失败 {len(self.errors)}"]
        lines += [f"- {e}" for e in self.errors[:10]]
        if len(self.errors) > 10:
            lines.append(f"- ……另有 {len(self.errors) - 10} 条错误未显示")
        return "\n".join(lines)


def _cell_time(value) -> Optional[str]:
    """单元格时间 → 'YYYY-MM-DD HH:MM'；支持 datetime 与常见文本格式。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    s = str(value).strip().replace("T", " ").replace("/", "-")
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:00", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None


def read_rows(path: str) -> list[dict]:
    """读取 xlsx 中的任务行（不做业务校验），返回 dict 列表。"""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    # 兼容列顺序差异：按表头名取列索引
    idx = {name: i for i, name in enumerate(HEADERS)}
    out = []
    for r in rows[1:]:
        if r is None or all(v is None or str(v).strip() == "" for v in r):
            continue  # 跳过空行
        first = str(r[0]).strip() if r and r[0] is not None else ""
        if first.startswith("导出时间"):
            continue  # 跳过末尾元信息行
        def get(name, default=""):
            i = idx.get(name)
            if i is None or i >= len(r):
                return default
            v = r[i]
            return "" if v is None else v
        name = str(get("任务名称")).strip()
        assignee = str(get("执行人")).strip()
        if not name and not assignee and get("截止时间") in (None, ""):
            continue  # 稀疏行视为空行
        out.append({
            "name": name,
            "assignee": assignee,
            "content": str(get("任务内容")),
            "deadline": get("截止时间"),
            "reminder_time": get("提醒时间"),
            "status": str(get("状态")).strip() or STATUS_DEFAULT,
            "notes": str(get("备注")),
            "created_at": get("创建时间"),
        })
    return out


def import_tasks(path: str, strategy: str = "skip") -> ImportReport:
    """导入 xlsx。strategy: skip=跳过重复 / overwrite=覆盖重复。

    内容列为纯文本；导入后保存为普通文本（非 HTML）。
    """
    report = ImportReport()
    from . import repository as repo
    from .models import TaskStatus

    rows = read_rows(path)
    report.total = len(rows)
    for n, row in enumerate(rows, start=2):   # Excel 行号（含表头）
        try:
            name = row["name"]
            assignee = row["assignee"]
            content = row["content"]
            deadline = _cell_time(row["deadline"])
            reminder = _cell_time(row["reminder_time"])
            if not name or not assignee:
                raise ValueError("任务名称/执行人为空")
            if deadline is None:
                raise ValueError("截止时间缺失或格式无法识别")
            if reminder is None:
                raise ValueError("提醒时间缺失或格式无法识别")
            status = row["status"]
            if status not in TaskStatus.ALL:
                status = STATUS_DEFAULT

            dup = repo.find_duplicate(name, assignee, deadline)
            if dup is not None:
                if strategy == "overwrite":
                    repo.update_task(dup.id, name=name, assignee=assignee, content=content,
                                     deadline=deadline, reminder_time=reminder,
                                     status=status if dup.status == status else dup.status,
                                     notes=row["notes"])
                    report.updated += 1
                else:
                    report.skipped += 1
                continue
            repo.add_task(name=name, assignee=assignee, content=content, deadline=deadline,
                          reminder_time=reminder, status=status, notes=row["notes"])
            report.added += 1
        except Exception as e:
            report.errors.append(f"第 {n} 行：{e}")
    return report
