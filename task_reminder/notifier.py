"""提醒通知：系统托盘 + 置顶提醒弹窗（含用户响应记录）。"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QMenu, QPushButton,
                             QSystemTrayIcon, QTextBrowser, QVBoxLayout)

from . import app_config, db, repository
from .models import Task, fmt, parse
from .sound import SoundPlayer


def app_icon() -> QIcon:
    """应用图标：开发态用根目录 app.ico，打包后用 assets/app.ico。"""
    candidates = [
        Path("app.ico"),
        Path(__file__).resolve().parent.parent / "app.ico",
        app_config.assets_dir() / "app.ico",
    ]
    for p in candidates:
        if p.exists():
            return QIcon(str(p))
    return QIcon()


def remaining_text(deadline: str) -> str:
    dl = parse(deadline)
    if not dl:
        return ""
    total = int((dl - datetime.now()).total_seconds())
    sign = "已过期" if total < 0 else "剩余"
    total = abs(total)
    days, rem = total // 86400, total % 86400
    if days:
        return f"{sign} {days} 天 {rem // 3600} 小时"
    return f"{sign} {rem // 3600} 小时 {(rem % 3600) // 60} 分钟"


class ReminderDialog(QDialog):
    """模态提醒弹窗：任务详情 + 稍后提醒 / 标记完成 / 关闭。"""

    def __init__(self, task: Task, history_id: int, parent=None):
        super().__init__(parent)
        self.task = task
        self.history_id = history_id
        self.response = ""
        self.setWindowTitle("任务提醒")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(420, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        head = QLabel(f"任务提醒：{task.summary()}")
        head.setObjectName("reminderTitle")
        head.setWordWrap(True)
        layout.addWidget(head)

        info = QLabel(f"执行人：{task.assignee}　　截止：{task.deadline}　　{remaining_text(task.deadline)}")
        info.setWordWrap(True)
        layout.addWidget(info)

        body = QTextBrowser()
        body.setPlainText((task.plain_text() or task.notes or "（无详细内容）")[:2000])
        layout.addWidget(body, 1)

        btns = QHBoxLayout()
        btn_snooze = QPushButton("稍后提醒")
        btn_done = QPushButton("标记完成")
        btn_close = QPushButton("关闭")
        btn_snooze.setObjectName("btnPrimary")
        btn_done.setObjectName("btnSuccess")
        snooze_menu = QMenu(btn_snooze)
        for minutes in (5, 10, 30, 60):
            snooze_menu.addAction(
                f"{minutes} 分钟后", lambda m=minutes: self._respond_snooze(m))
        btn_snooze.setMenu(snooze_menu)
        btn_snooze.setToolTip("选择稍后再次提醒的间隔")
        btn_snooze.clicked.connect(lambda: self._respond_snooze(5))
        btn_done.clicked.connect(lambda: self._respond("done"))
        btn_close.clicked.connect(lambda: self._respond("close"))
        btns.addWidget(btn_snooze)
        btns.addWidget(btn_done)
        btns.addStretch(1)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _respond_snooze(self, minutes: int) -> None:
        self._respond("snooze", minutes=minutes)

    def _respond(self, response: str, minutes: int = 5) -> None:
        self.response = response
        if self.history_id:
            repository.set_history_response(self.history_id, response)
        if response == "done" and self.task.id:
            repository.set_status(self.task.id, "已完成")
        elif response == "snooze" and self.task.id:
            self._snooze(minutes)
        self.accept()

    def _snooze(self, minutes: int) -> None:
        """稍后提醒：提醒时间顺延 N 分钟并允许再次触发。"""
        base = parse(self.task.reminder_time) or datetime.now()
        new_time = max(base, datetime.now()) + timedelta(minutes=minutes)
        now = fmt(datetime.now())
        with db.transaction() as c:
            c.execute(
                "UPDATE tasks SET reminder_time=?, triggered=0, updated_at=? WHERE id=?",
                (fmt(new_time), now, self.task.id),
            )


class Notifier(QObject):
    """提醒队列：声音 + 托盘气泡 + 逐个弹窗。"""

    queue_changed = pyqtSignal(int)      # 待处理提醒数量
    responded = pyqtSignal(str)          # 用户在弹窗做出响应（snooze/done/close）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sound = SoundPlayer()
        self.tray: QSystemTrayIcon | None = None
        self._queue: list[tuple[Task, int]] = []
        self._dialog: ReminderDialog | None = None

    def setup_tray(self, tray: QSystemTrayIcon) -> None:
        self.tray = tray

    def notify(self, task: Task, history_id: int) -> None:
        """入队一条提醒：先声音/气泡，弹窗由 pump 逐个展示。"""
        self._queue.append((task, history_id))
        self._play_sound()
        if self.tray is not None:
            active = QApplication.activeWindow()
            if active is None or active.isMinimized():
                self.tray.showMessage(
                    "任务提醒",
                    f"{task.summary()}\n执行人：{task.assignee}　截止：{task.deadline}",
                    QSystemTrayIcon.MessageIcon.Information, 8000,
                )
        self._emit()

    def _play_sound(self) -> None:
        self.sound.play(enabled=bool(app_config.get("sound_enabled", True)))

    def pump(self) -> None:
        """展示下一个提醒弹窗（前一个关闭后继续）。"""
        if self._dialog is not None or not self._queue:
            return
        task, hid = self._queue.pop(0)
        self._dialog = ReminderDialog(task, hid)
        self._dialog.accepted.connect(self._on_dialog_done)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()
        self._emit()

    def _on_dialog_done(self) -> None:
        dlg, self._dialog = self._dialog, None
        self._emit()
        if dlg is not None and dlg.response:
            self.responded.emit(dlg.response)
        # 队列里还有待展示的提醒 → 立即弹出下一个（否则要等下一轮轮询）
        self.pump()

    def _emit(self) -> None:
        self.queue_changed.emit(self.pending_count())

    def pending_count(self) -> int:
        n = len(self._queue)
        if self._dialog is not None:
            n += 1
        return n
