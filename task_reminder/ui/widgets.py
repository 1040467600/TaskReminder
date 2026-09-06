"""通用组件：分页栏、状态徽章、操作按钮、列配置。"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QPushButton, QSpinBox,
                             QStyledItemDelegate, QToolButton, QWidget)

from ..models import Task, TaskStatus

# 状态 → (背景色, 文本色)
STATUS_COLORS = {
    TaskStatus.NOT_STARTED: ("#64748B", "#FFFFFF"),
    TaskStatus.IN_PROGRESS: ("#2563EB", "#FFFFFF"),
    TaskStatus.DONE: ("#16A34A", "#FFFFFF"),
}

# 列定义：(id, 标题, 默认可见, 默认宽度)
COLUMNS = [
    ("name", "任务名称", True, 220),
    ("content", "任务内容", True, 280),
    ("assignee", "执行人", True, 100),
    ("deadline", "截止时间", True, 150),
    ("reminder_time", "提醒时间", True, 150),
    ("status", "状态", True, 96),
    ("notes", "备注", False, 180),
    ("actions", "操作", True, 132),
]

ACTION_EDIT, ACTION_DELETE = "edit", "delete"


def confirm(parent, title: str, text: str) -> bool:
    """中文按钮确认弹窗（Qt 默认 Yes/No 在中文界面下不友好）。"""
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    btn_ok = box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_ok)
    box.exec()
    return box.clickedButton() is btn_ok


class StatusDelegate(QStyledItemDelegate):
    """状态列徽章绘制。"""

    def paint(self, painter: QPainter, option, index):
        status = index.data(Qt.ItemDataRole.UserRole)
        if not status:
            super().paint(painter, option, index)
            return
        bg, fg = STATUS_COLORS.get(status, ("#64748B", "#FFFFFF"))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        text = str(status)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(text) + 20
        h = metrics.height() + 6
        x = rect.x() + max(4, (rect.width() - w) // 2)
        y = rect.y() + max(2, (rect.height() - h) // 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(QRect(x, y, w, h), h // 2, h // 2)
        painter.setPen(QColor(fg))
        painter.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class ActionDelegate(QStyledItemDelegate):
    """操作列：编辑 / 删除 两个内联按钮（仅绘制+命中测试，轻量）。"""

    action = pyqtSignal(object, str)   # (task_id, action)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        text, text2 = "编辑", "删除"
        f = option.font
        painter.setFont(f)
        rect = option.rect
        btn_w, btn_h = 52, min(26, rect.height() - 8)
        y = rect.y() + (rect.height() - btn_h) // 2
        r1 = QRect(rect.x() + 8, y, btn_w, btn_h)
        r2 = QRect(rect.x() + 8 + btn_w + 8, y, btn_w, btn_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EFF6FF"))
        painter.drawRoundedRect(r1, 5, 5)
        painter.setBrush(QColor("#FEF2F2"))
        painter.drawRoundedRect(r2, 5, 5)
        painter.setPen(QColor("#2563EB"))
        painter.drawText(r1, Qt.AlignmentFlag.AlignCenter, text)
        painter.setPen(QColor("#DC2626"))
        painter.drawText(r2, Qt.AlignmentFlag.AlignCenter, text2)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonRelease:
            rect = option.rect
            btn_w = 52
            x1 = rect.x() + 8
            x2 = x1 + btn_w + 8
            if rect.x() <= event.position().toPoint().x() <= rect.x() + rect.width():
                px = event.position().toPoint().x()
                task_id = index.data(Qt.ItemDataRole.UserRole)
                if task_id is None:
                    return False
                if x1 <= px <= x1 + btn_w:
                    self.action.emit(task_id, ACTION_EDIT)
                    return True
                if x2 <= px <= x2 + btn_w:
                    self.action.emit(task_id, ACTION_DELETE)
                    return True
        return False


def deadline_foreground(task: Task) -> QColor | None:
    """过期未完成 → 红色。"""
    if task.is_overdue(datetime.now()):
        return QColor("#DC2626")
    return None


class PaginationBar(QWidget):
    """分页栏：首页/上一页/页码信息/下一页/末页 + 跳页 + 每页条数。"""

    page_changed = pyqtSignal(int)          # 当前页
    page_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.btn_first = QPushButton("首页")
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.btn_last = QPushButton("末页")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setObjectName("btnRow")
        self.lbl_info = QLabel("共 0 条")
        self.cmb_size = QToolButton()
        self.cmb_size.setText("每页 200")
        self.cmb_size.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self)
        for n in (50, 100, 200, 500):
            self._menu.addAction(f"每页 {n}", lambda n=n: self._set_size(n))
        self.cmb_size.setMenu(self._menu)
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addStretch(1)
        layout.addWidget(self.lbl_info)
        layout.addWidget(QLabel("跳至"))
        self.spin_page = QSpinBox()
        self.spin_page.setRange(1, 1)
        self.spin_page.setMaximumWidth(70)
        self.spin_page.setToolTip("输入页码后按回车跳转")
        self.spin_page.editingFinished.connect(self._on_jump)
        layout.addWidget(self.spin_page)
        layout.addWidget(QLabel("页"))
        layout.addStretch(1)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        layout.addWidget(self.cmb_size)
        self.page, self.total, self.size = 1, 0, 200
        self.btn_first.clicked.connect(lambda: self._go(1))
        self.btn_prev.clicked.connect(lambda: self._go(self.page - 1))
        self.btn_next.clicked.connect(lambda: self._go(self.page + 1))
        self.btn_last.clicked.connect(lambda: self._go(10 ** 9))

    def _set_size(self, n: int):
        self.size = n
        self.cmb_size.setText(f"每页 {n}")
        self.page_size_changed.emit(n)

    def _on_jump(self):
        self._go(self.spin_page.value())

    def _go(self, p: int):
        pages = max(1, (self.total + self.size - 1) // self.size)
        p = max(1, min(p, pages))
        if p != self.page:
            self.page = p
            self.page_changed.emit(p)

    def update_info(self, total: int, page: int, size: int):
        self.total, self.page, self.size = total, page, size
        pages = max(1, (total + size - 1) // size)
        self.lbl_info.setText(f"共 {total} 条　第 {page}/{pages} 页")
        self.spin_page.blockSignals(True)
        self.spin_page.setRange(1, pages)
        self.spin_page.setValue(page)
        self.spin_page.blockSignals(False)
        self.cmb_size.setText(f"每页 {size}")
        self.btn_first.setEnabled(page > 1)
        self.btn_prev.setEnabled(page > 1)
        self.btn_next.setEnabled(page < pages)
        self.btn_last.setEnabled(page < pages)
