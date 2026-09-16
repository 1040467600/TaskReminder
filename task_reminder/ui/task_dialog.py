"""新建/编辑任务对话框：富文本编辑 + 实时字段校验。"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QDateTime, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QFont, QPixmap, QTextCharFormat
from PyQt6.QtWidgets import (QComboBox, QCompleter, QDateTimeEdit, QDialog, QFileDialog,
                             QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from .. import repository
from ..models import CONTENT_MAX, NAME_MAX, NAME_MIN, NOTES_MAX, Task, TaskStatus, plain_len


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
        self.edit_name.setPlaceholderText("1-50 个字符")
        form.addRow("任务名称：", self.edit_name)

        # 执行人（历史人员自动补全）
        self.edit_assignee = QLineEdit()
        self.edit_assignee.setMaxLength(NAME_MAX)
        self.edit_assignee.setPlaceholderText("1-50 个字符")
        names = repository.list_assignees()
        if names:
            completer = QCompleter(names, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.edit_assignee.setCompleter(completer)
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
        self.btn_bold.setToolTip("加粗（Ctrl+B）")
        self.btn_italic.setToolTip("斜体（Ctrl+I）")
        self.btn_underline.setToolTip("下划线（Ctrl+U）")
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
        self.edit_content.currentCharFormatChanged.connect(self._on_fmt_changed)
        content_box.addWidget(self.edit_content)
        form.addRow("任务内容：", content_box)

        # 时间（快捷预设 + 自动联动：始终保证提醒早于截止）
        self.dt_deadline = QDateTimeEdit()
        self.dt_deadline.setCalendarPopup(True)
        self.dt_deadline.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_deadline.dateTimeChanged.connect(self._on_deadline_changed)
        form.addRow("截止时间：", self._time_row(self.dt_deadline, deadline=True))

        self.dt_reminder = QDateTimeEdit()
        self.dt_reminder.setCalendarPopup(True)
        self.dt_reminder.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_reminder.dateTimeChanged.connect(self._on_reminder_changed)
        form.addRow("提醒时间：", self._time_row(self.dt_reminder, deadline=False))

        # 状态与备注
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(list(TaskStatus.ALL))
        form.addRow("状态：", self.cmb_status)

        self.edit_notes = QPlainTextEdit()
        self.edit_notes.setMaximumHeight(64)
        self.edit_notes.setPlaceholderText(f"备注（可选，最多 {NOTES_MAX} 字）")
        self.edit_notes.textChanged.connect(self._on_notes_changed)
        notes_box = QVBoxLayout()
        notes_box.setSpacing(2)
        notes_box.addWidget(self.edit_notes)
        self.lbl_notes = QLabel("0 / " + str(NOTES_MAX))
        self.lbl_notes.setObjectName("tagNote")
        self.lbl_notes.setAlignment(Qt.AlignmentFlag.AlignRight)
        notes_box.addWidget(self.lbl_notes)
        form.addRow("备注：", notes_box)

        layout.addLayout(form)

        # 佐证图片（任务完成凭证，可多张；新建时先暂存路径，保存成功后入库）
        self._pending_images: list[str] = []   # 新建/编辑后尚未入库的本地图片路径
        self._images = []                       # 已入库的 TaskImage
        layout.addWidget(self._build_images_box())

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
    # 佐证图片
    def _build_images_box(self) -> QWidget:
        box = QGroupBox("佐证图片（任务完成凭证，可添加多张，支持 jpg/png/gif/bmp/webp）")
        outer = QVBoxLayout(box)
        outer.setSpacing(6)
        row = QHBoxLayout()
        self.lbl_images_count = QLabel("共 0 张")
        self.lbl_images_count.setObjectName("tagNote")
        btn_add = QPushButton("＋ 添加图片")
        btn_add.setObjectName("btnRow")
        btn_add.clicked.connect(self._pick_images)
        row.addWidget(self.lbl_images_count)
        row.addStretch(1)
        row.addWidget(btn_add)
        outer.addLayout(row)

        self.images_scroll = QScrollArea()
        self.images_scroll.setWidgetResizable(True)
        self.images_scroll.setFixedHeight(150)
        self.images_host = QWidget()
        self.images_grid = QGridLayout(self.images_host)
        self.images_grid.setContentsMargins(2, 2, 2, 2)
        self.images_grid.setSpacing(8)
        self.images_scroll.setWidget(self.images_host)
        outer.addWidget(self.images_scroll)
        return box

    def _reload_images(self):
        """重建缩略图网格（已入库 + 待保存）。"""
        while self.images_grid.count():
            w = self.images_grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        entries = [("saved", im) for im in self._images]
        entries += [("pending", p) for p in self._pending_images]
        self.lbl_images_count.setText(f"共 {len(entries)} 张")
        cols = 4
        for i, (kind, ref) in enumerate(entries):
            path = str(repository.image_path(ref)) if kind == "saved" else ref
            cell = self._image_cell(kind, ref, path)
            self.images_grid.addWidget(cell, i // cols, i % cols)

    def _image_cell(self, kind: str, ref, path: str) -> QWidget:
        cell = QWidget()
        v = QVBoxLayout(cell)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        thumb = QLabel()
        thumb.setFixedSize(108, 84)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("border:1px solid #CBD5E1; border-radius:4px; background:#F8FAFC;")
        pm = QPixmap(path)
        name = ref.filename if kind == "saved" else Path(ref).name
        if not pm.isNull():
            thumb.setPixmap(pm.scaled(104, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        else:
            thumb.setText("无法预览")
        thumb.setToolTip(name)
        v.addWidget(thumb)
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(2)
        b_open = QPushButton("打开")
        b_save = QPushButton("另存")
        b_del = QPushButton("删除")
        for b in (b_open, b_save, b_del):
            b.setObjectName("btnRow")
            b.setFixedHeight(20)
        b_open.clicked.connect(lambda: self._open_image(path))
        b_save.clicked.connect(lambda: self._download_image(path, name))
        b_del.clicked.connect(lambda: self._remove_image(kind, ref))
        btns.addWidget(b_open)
        btns.addWidget(b_save)
        btns.addWidget(b_del)
        v.addLayout(btns)
        return cell

    def _pick_images(self):
        """多选导入图片；校验格式/大小后加入待保存列表。"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择佐证图片（可多选）", "",
            "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp)")
        added = 0
        for p in paths:
            src = Path(p)
            if p in self._pending_images:
                continue
            if src.suffix.lower() not in repository.IMAGE_EXTS:
                QMessageBox.warning(self, "图片格式不支持", f"{src.name} 不是受支持的图片格式。")
                continue
            try:
                size = src.stat().st_size
            except OSError:
                QMessageBox.warning(self, "图片无法读取", f"{src.name} 文件无法访问。")
                continue
            if size > repository.IMAGE_MAX_BYTES:
                QMessageBox.warning(self, "图片过大",
                                    f"{src.name} 超过 "
                                    f"{repository.IMAGE_MAX_BYTES // 1024 // 1024}MB 上限。")
                continue
            self._pending_images.append(p)
            added += 1
        if added:
            self._reload_images()

    @staticmethod
    def _open_image(path: str):
        """用系统默认图片查看器打开（下载/查看）。"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _download_image(self, path: str, suggested_name: str):
        """另存为：把图片下载到用户指定位置。"""
        dest, _ = QFileDialog.getSaveFileName(self, "图片另存为", suggested_name,
                                              "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp)")
        if not dest:
            return
        try:
            import shutil
            shutil.copy2(path, dest)
        except OSError as e:
            QMessageBox.warning(self, "保存失败", f"图片另存失败：{e}")
            return
        QMessageBox.information(self, "保存成功", f"图片已保存到：\n{dest}")

    def _remove_image(self, kind: str, ref):
        """删除图片：已入库的立即删记录+文件；待保存的移出暂存列表。"""
        if kind == "saved":
            if repository.delete_task_image(ref.id):
                self._images = [im for im in self._images if im.id != ref.id]
        else:
            self._pending_images = [p for p in self._pending_images if p != ref]
        self._reload_images()

    def _save_pending_images(self) -> list[str]:
        """保存成功后把待入库图片复制入库。返回错误信息列表。"""
        errors = []
        for src in self._pending_images:
            try:
                repository.add_task_image(self.task_id, src)
            except Exception as e:
                errors.append(f"{Path(src).name}：{e}")
        self._pending_images.clear()
        return errors

    # ------------------------------------------------------------------
    def _default_times(self):
        now = datetime.now()
        reminder = now.replace(second=0, microsecond=0)
        # 截止 = 提醒 + 1 小时：任何时刻打开都满足"提醒早于截止"，
        # 避免 23 点后默认截止时间落在提醒之前导致一打开就校验失败
        deadline = reminder + timedelta(hours=1)
        self.dt_deadline.setDateTime(deadline)
        self.dt_reminder.setDateTime(reminder)

    # ------------------------------------------------------------------
    # 时间快捷预设与联动
    def _time_row(self, edit: QDateTimeEdit, deadline: bool) -> QWidget:
        """时间输入框 + '快捷 ▾' 预设菜单。"""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        btn = QToolButton()
        btn.setText("快捷 ▾")
        btn.setObjectName("btnRow")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn)
        now = datetime.now().replace(second=0, microsecond=0)
        if deadline:
            next_mon = (now + timedelta(days=7 - now.weekday())).replace(hour=9, minute=0)
            presets = [
                ("今天 18:00", now.replace(hour=18, minute=0)),
                ("明天 09:00", (now + timedelta(days=1)).replace(hour=9, minute=0)),
                ("明天 18:00", (now + timedelta(days=1)).replace(hour=18, minute=0)),
                ("3 天后此刻", now + timedelta(days=3)),
                ("7 天后此刻", now + timedelta(days=7)),
                ("下周一 09:00", next_mon),
            ]
        else:
            presets = [
                ("30 分钟后", now + timedelta(minutes=30)),
                ("1 小时后", now + timedelta(hours=1)),
                ("明天 09:00", (now + timedelta(days=1)).replace(hour=9, minute=0)),
                ("截止前 1 小时", None),
            ]
        for text, dt in presets:
            menu.addAction(text, lambda dt=dt: self._apply_preset(edit, deadline, dt))
        btn.setMenu(menu)
        h.addWidget(edit, 1)
        h.addWidget(btn)
        return row

    def _apply_preset(self, edit: QDateTimeEdit, deadline: bool, dt: datetime | None):
        if dt is None:   # 截止前 1 小时
            base = self.dt_deadline.dateTime().toPyDateTime() - timedelta(hours=1)
            dt = max(base, datetime.now().replace(second=0, microsecond=0))
        edit.setDateTime(QDateTime(dt))

    def _on_deadline_changed(self, dt: QDateTime):
        # 截止被改到不晚于提醒 → 提醒自动前移 1 小时，保持"提醒早于截止"
        if dt <= self.dt_reminder.dateTime():
            self.dt_reminder.blockSignals(True)
            self.dt_reminder.setDateTime(dt.addSecs(-3600))
            self.dt_reminder.blockSignals(False)

    def _on_reminder_changed(self, dt: QDateTime):
        # 提醒被改到不早于截止 → 截止自动后移 1 小时
        if dt >= self.dt_deadline.dateTime():
            self.dt_deadline.blockSignals(True)
            self.dt_deadline.setDateTime(dt.addSecs(3600))
            self.dt_deadline.blockSignals(False)

    # ------------------------------------------------------------------
    def _on_notes_changed(self):
        text = self.edit_notes.toPlainText()
        if len(text) > NOTES_MAX:
            pos = self.edit_notes.textCursor().position()
            self.edit_notes.setPlainText(text[:NOTES_MAX])
            cursor = self.edit_notes.textCursor()
            cursor.setPosition(min(pos, NOTES_MAX))
            self.edit_notes.setTextCursor(cursor)
        self.lbl_notes.setText(f"{min(len(text), NOTES_MAX)} / {NOTES_MAX}")

    def _load(self, t: Task):
        self.edit_name.setText(t.name)
        self.edit_assignee.setText(t.assignee)
        self.edit_content.setHtml(t.content or "")
        self.dt_deadline.setDateTime(QDateTime.fromString(t.deadline, "yyyy-MM-dd HH:mm"))
        self.dt_reminder.setDateTime(QDateTime.fromString(t.reminder_time, "yyyy-MM-dd HH:mm"))
        self.cmb_status.setCurrentText(t.status)
        self.edit_notes.setPlainText(t.notes or "")
        self._images = repository.list_task_images(t.id)
        self._reload_images()
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
        if cursor.hasSelection():
            # 选中文字：合并格式到选区
            cursor.mergeCharFormat(cf)
            self.edit_content.setTextCursor(cursor)
        else:
            # 无选中：修改当前输入格式（注意 merge() 原地修改且返回 None，
            # 不能把返回值直接传入 setCurrentCharFormat，否则槽内 TypeError 会终止进程）
            fmt = self.edit_content.currentCharFormat()
            fmt.merge(cf)
            self.edit_content.setCurrentCharFormat(fmt)
        self._sync_fmt_buttons()

    def _clear_fmt(self):
        fmt = QTextCharFormat()
        cursor = self.edit_content.textCursor()
        if cursor.hasSelection():
            cursor.setCharFormat(fmt)
            self.edit_content.setTextCursor(cursor)
        # 无选中时也重置当前输入格式（QTextCursor.setCharFormat 只作用于选区）
        self.edit_content.setCurrentCharFormat(fmt)
        self._sync_fmt_buttons()

    def _sync_fmt_buttons(self):
        """让 B/I/U 按钮的按下状态跟随光标处字符格式。"""
        f = self.edit_content.currentCharFormat()
        for btn, on in ((self.btn_bold, f.fontWeight() == QFont.Weight.Bold),
                        (self.btn_italic, f.fontItalic()),
                        (self.btn_underline, f.fontUnderline())):
            if btn.isChecked() != on:
                btn.blockSignals(True)
                btn.setChecked(on)
                btn.blockSignals(False)

    def _on_fmt_changed(self, fmt):
        self._sync_fmt_buttons()

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
        if len(name) < NAME_MIN:
            err = f"任务名称至少 {NAME_MIN} 个字符"
        elif len(assignee) < NAME_MIN:
            err = f"执行人姓名至少 {NAME_MIN} 个字符"
        elif plain_len(self.edit_content.toHtml()) > CONTENT_MAX:
            err = f"任务内容最多 {CONTENT_MAX} 字"
        elif len(self.edit_notes.toPlainText()) > NOTES_MAX:
            err = f"备注最多 {NOTES_MAX} 字"
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
        # 任务已落库（拿到 task_id），把本次新选的佐证图片复制入库
        errors = self._save_pending_images()
        self.accept()
        if errors:
            QMessageBox.warning(self, "部分图片未保存",
                                "以下图片保存失败：\n" + "\n".join(errors))

    @classmethod
    def edit(cls, parent, task: Task) -> bool:
        dlg = cls(parent, editing_task=task)
        return dlg.exec() == 1
