"""数据模型：任务与提醒记录。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

TIME_FMT = "%Y-%m-%d %H:%M"

# 名称/执行人长度限制（字符）
NAME_MIN, NAME_MAX = 1, 50
# 任务内容纯文本最大长度
CONTENT_MAX = 5000


class TaskStatus:
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    DONE = "已完成"

    ALL = (NOT_STARTED, IN_PROGRESS, DONE)


# 状态排序权重（用于 SQL CASE 排序）
STATUS_SORT_ORDER = {TaskStatus.NOT_STARTED: 0, TaskStatus.IN_PROGRESS: 1, TaskStatus.DONE: 2}

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&[a-z]+;|&#\d+;")


def html_to_plain(html: str) -> str:
    """将富文本 HTML 转为纯文本（用于摘要与导出）。"""
    if not html:
        return ""
    if "<" not in html and "&" not in html:   # 纯文本快速路径
        return html
    text = re.sub(r"<(style|script|head)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<!DOCTYPE[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", text, flags=re.I)
    text = _TAG_RE.sub("", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
    )
    text = _ENTITY_RE.sub("", text)
    return text.strip()


def plain_len(html: str) -> int:
    """富文本内容的纯文本长度（用于 5000 字限制）。"""
    return len(html_to_plain(html))


def fmt(dt: datetime) -> str:
    return dt.strftime(TIME_FMT)


def parse(s: str) -> Optional[datetime]:
    """解析时间字符串，兼容 'T' 分隔与含秒格式。"""
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for f in (TIME_FMT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


@dataclass
class Task:
    id: Optional[int] = None
    name: str = ""
    assignee: str = ""
    content: str = ""          # 富文本 HTML
    deadline: str = ""         # YYYY-MM-DD HH:MM
    reminder_time: str = ""    # YYYY-MM-DD HH:MM
    status: str = TaskStatus.NOT_STARTED
    notes: str = ""
    triggered: int = 0
    status_changed_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def content_plain(self) -> str:
        return html_to_plain(self.content)

    def summary(self, limit: int = 40) -> str:
        """任务名称/摘要列显示文本：优先名称，否则内容摘要。"""
        text = (self.name or "").strip()
        if not text:
            text = self.content_plain().replace("\n", " ")
        return text[:limit] + ("…" if len(text) > limit else "")

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now()
        dl = parse(self.deadline)
        return bool(dl and dl < now and self.status != TaskStatus.DONE)

    @classmethod
    def from_row(cls, row) -> "Task":
        keys = row.keys() if hasattr(row, "keys") else []
        data = {k: row[k] for k in keys}
        return cls(**data)


@dataclass
class ReminderLog:
    id: Optional[int] = None
    task_id: Optional[int] = None
    triggered_at: str = ""
    assignee: str = ""
    content_snapshot: str = ""
    deadline: str = ""
    response: str = ""          # ''=未响应 / snooze=稍后提醒 / done=标记完成 / close=关闭
    responded_at: str = ""
    acknowledged: int = 0

    RESPONSE_TEXT = {"": "未响应", "snooze": "稍后提醒", "done": "标记完成", "close": "关闭"}

    def response_text(self) -> str:
        return self.RESPONSE_TEXT.get(self.response, self.response)

    @classmethod
    def from_row(cls, row) -> "ReminderLog":
        keys = row.keys() if hasattr(row, "keys") else []
        data = {k: row[k] for k in keys}
        return cls(**data)
