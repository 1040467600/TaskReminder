"""新建/编辑任务对话框：富文本编辑 + 实时字段校验。"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCharFormat
from PyQt6.QtWidgets import (QComboBox, QDateTimeEdit, QDialog, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton, QPlainTextEdit,
                             QTextEdit, QVBoxLayout)

from .. import repository
from ..models import CONTENT_MAX, NAME_MAX, Task, TaskStatus, plain_len


class TaskDialog(QDialog):
    """新建 / 编辑任务。editing_task 为 None 表示新建。"""

    def __init__(self, parent=None, editing_task: Task | None = None):
        super().__init__(parent)
        self.editing = editing_task
        self.task_id = editing_task.id if editing_task else None
        self.setWindowTitle("编辑任务" if editing_task else "新建任务")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)

        # 名称
        self.edit_name = QLineEdit()
        self.edit_name.setMaxLength(NAME_MAX)
        self.edit_name.setPlaceholderText("2-50 个字符")
        form.addRow("任务名称：", self.edit_name)

        # 执行人
        self.edit_assignee = QLineEdit()
        self.edit_assignee.setMaxLength(NAME_MAX)
        self.edit_assignee.setPlaceholderText("2-50 个字符")
        form.addRow("执行人：", self.edit_assignee)

        # 富文本内容
        content_box = QVBoxLayout()
        toolbar = QHBoxLayout()
        self.btn_bold = QPushButton("B")
        self.btn_italic = QPushButton("I")
        self.btn_underline = QPushButton("U")
        self.btn_clear_fmt = QPushButton("清除格式")
        for b in (self.btn_bold, self.btn_italic, self.btn_underline):
            b.setCheckable(True)
            b.setObjectName("btnRow")
            b.setMaximumWidth(34)
        self.btn_clear_fmt.setObjectName("btnRow")
        self.btn_bold.clicked.connect(lambda: self._fmt(bold=self.btn_bold.isChecked()))
        self.btn_italic.clicked.connect(lambda: self._fmt(italic=self.btn_italic.isChecked()))
        self.btn_underline.clicked.connect(lambda: self._fmt(underline=self.btn_underline.isChecked()))
        self.btn_clear_fmt.clicked.connect(self._clear_fmt)
        toolbar.addWidget(self.btn_bold)
        toolbar.addWidget(self.btn_italic)
        toolbar.addWidget(self.btn_underline)
        toolbar.addWidget(self.btn_clear_fmt)
        toolbar.addStretch(1)
        self.lbl_count = QLabel("0 / 5000")
        self.lbl_count.setObjectName("tagNote")
        toolbar.addWidget(self.lbl_count)
        content_box.addLayout(toolbar)

        self.edit_content = QTextEdit()
        self.edit_content.setAcceptRichText(True)
        self.edit_content.setMinimumHeight(120)
        self.edit_content.setPlaceholderText("支持富文本：加粗 / 斜体 / 下划线，最多 5000 字")
        self.edit_content.textChanged.connect(self._on_content_changed)
        content_box.addWidget(self.edit_content)
        form.addRow("任务内容：", content_box)

        # 时间
        self.dt_deadline = QDateTimeEdit()
        self.dt_deadline.setCalendarPopup(True)
        self.dt_deadline.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("截止时间：", self.dt_deadline)

        self.dt_reminder = QDateTimeEdit()
        self.dt_reminder.setCalendarPopup(True)
        self.dt_reminder.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("提醒时间：", self.dt_reminder)

        # 状态与备注
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(list(TaskStatus.ALL))
        form.addRow("状态：", self.cmb_status)

        self.edit_notes = QPlainTextEdit()
        self.edit_notes.setMaximumHeight(64)
        self.edit_notes.setPlaceholderText("备注（可选）")
        form.addRow("备注：", self.edit_notes)

        layout.addLayout(form)

        # 校验提示
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #DC2626;")
        layout.addWidget(self.lbl_error)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_ok = QPushButton("保存")
        self.btn_ok.setObjectName("btnPrimary")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        # 实时校验
        for w in (self.edit_name, self.edit_assignee):
            w.textChanged.connect(self._validate)
        self.dt_deadline.dateTimeChanged.connect(self._validate)
        self.dt_reminder.dateTimeChanged.connect(self._validate)

        if editing_task:
            self._load(editing_task)
        else:
            self._default_times()

    # ------------------------------------------------------------------
    def _default_times(self):
        now = datetime.now()
        self.dt_deadline.setDateTime(now.replace(minute=0, second=0, microsecond=0)
                                     .replace(hour=now.hour + 1 if now.hour < 23 else now.hour))
        self.dt_reminder.setDateTime(now.replace(second=0, microsecond=0))

    def _load(self, t: Task):
        self.edit_name.setText(t.name)
        self.edit_assignee.setText(t.assignee)
        self.edit_content.setHtml(t.content or "")
        from PyQt6.QtCore import QDateTime
        self.dt_deadline.setDateTime(QDateTime.fromString(t.deadline, "yyyy-MM-dd HH:mm"))
        self.dt_reminder.setDateTime(QDateTime.fromString(t.reminder_time, "yyyy-MM-dd HH:mm"))
        self.cmb_status.setCurrentText(t.status)
        self.edit_notes.setPlainText(t.notes or "")
        self._validate()

    # ------------------------------------------------------------------
    def _fmt(self, bold=None, italic=None, underline=None):
        cf = QTextCharFormat()
        if bold is not None:
            cf.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if italic is not None:
            cf.setFontItalic(italic)
        if underline is not None:
            cf.setFontUnderline(underline)
        cursor = self.edit_content.textCursor()
        if not cursor.hasSelection():
            self.edit_content.setCurrentCharFormat(
                self.edit_content.currentCharFormat().merge(cf))
        else:
            cursor.mergeCharFormat(cf)

    def _clear_fmt(self):
        cursor = self.edit_content.textCursor()
        cursor.setCharFormat(QTextCharFormat())

    def _on_content_changed(self):
        n = plain_len(self.edit_content.toHtml())
        self.lbl_count.setText(f"{n} / {CONTENT_MAX}")
        self.lbl_count.setStyleSheet("" if n <= CONTENT_MAX else "color: #DC2626;")
        self._validate()

    # ------------------------------------------------------------------
    def _validate(self) -> str | None:
        """返回第一条错误信息；无错误返回 None。"""
        name = self.edit_name.text().strip()
        assignee = self.edit_assignee.text().strip()
        err = None
        if len(name) < 2:
            err = "任务名称至少 2 个字符"
        elif len(assignee) < 2:
            err = "执行人姓名至少 2 个字符"
        elif plain_len(self.edit_content.toHtml()) > CONTENT_MAX:
            err = f"任务内容最多 {CONTENT_MAX} 字"
        else:
            dl, rt = self.dt_deadline.dateTime(), self.dt_reminder.dateTime()
            if rt >= dl:
                err = "提醒时间必须早于截止时间"
        self.lbl_error.setText(err or "")
        self.btn_ok.setEnabled(err is None)
        return err

    def _on_save(self):
        if self._validate() is not None:
            return
        try:
            kwargs = dict(
                name=self.edit_name.text().strip(),
                assignee=self.edit_assignee.text().strip(),
                content=self.edit_content.toHtml(),
                deadline=self.dt_deadline.dateTime().toString("yyyy-MM-dd HH:mm"),
                reminder_time=self.dt_reminder.dateTime().toString("yyyy-MM-dd HH:mm"),
                status=self.cmb_status.currentText(),
                notes=self.edit_notes.toPlainText(),
            )
            if self.task_id:
                repository.update_task(self.task_id, **kwargs)
            else:
                self.task_id = repository.add_task(**kwargs)
        except repository.ValidationError as e:
            QMessageBox.warning(self, "校验失败", str(e))
            return
        self.accept()

    @classmethod
    def edit(cls, parent, task: Task) -> bool:
        dlg = cls(parent, editing_task=task)
        return dlg.exec() == 1
