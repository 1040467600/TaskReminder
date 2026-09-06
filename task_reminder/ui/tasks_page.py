"""任务管理页：表格 + 排序可视化 + 列配置 + 分页 + 导入导出。"""
from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout,
                             QHeaderView, QLabel, QMenu, QMessageBox, QPushButton, QTableView,
                             QVBoxLayout, QWidget)

from .. import app_config, excel_io, repository
from ..models import Task
from .search_bar import SearchBar
from .task_dialog import TaskDialog
from .task_table_model import TaskTableModel
from .widgets import (ACTION_DELETE, ACTION_EDIT, COLUMNS, ActionDelegate, PaginationBar,
                      StatusDelegate)

COL_STATE_KEY = "column_state"


def _vsep() -> QFrame:
    """工具栏分组竖线。"""
    line = QFrame()
    line.setObjectName("vsep")
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    return line


class TasksPage(QWidget):
    data_changed = pyqtSignal()      # 通知其他页面刷新

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_no = 1
        self.sort_key = "created_at"
        self.sort_dir = "desc"          # '' 表示默认（未排序）
        self._build()
        self._restore_states()
        self.refresh()

    # ------------------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(10)

        # ===== 顶部卡片：工具栏 + 搜索 =====
        top_card = QWidget()
        top_card.setObjectName("card")
        cv = QVBoxLayout(top_card)
        cv.setContentsMargins(14, 12, 14, 12)
        cv.setSpacing(10)

        # 工具栏（按功能分组，竖线分隔）
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_new = QPushButton("＋ 新建任务")
        self.btn_new.setObjectName("btnPrimary")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit = QPushButton("编辑")
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setObjectName("btnDanger")
        self.btn_export = QPushButton("导出 Excel")
        self.btn_import = QPushButton("导入 Excel")
        self.btn_columns = QPushButton("列设置")
        self.btn_refresh = QPushButton("刷新")
        self.btn_new.clicked.connect(self.on_new)
        self.btn_edit.clicked.connect(self.on_edit_selected)
        self.btn_delete.clicked.connect(self.on_delete_selected)
        self.btn_export.clicked.connect(self.on_export)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_columns.clicked.connect(self._show_column_menu)
        for b in (self.btn_new, self.btn_edit, self.btn_delete):
            bar.addWidget(b)
        bar.addWidget(_vsep())
        for b in (self.btn_export, self.btn_import):
            bar.addWidget(b)
        bar.addWidget(_vsep())
        for b in (self.btn_columns, self.btn_refresh):
            bar.addWidget(b)
        bar.addStretch(1)
        cv.addLayout(bar)

        # 搜索
        self.search = SearchBar()
        self.search.changed.connect(self._on_search_changed)
        cv.addWidget(self.search)
        outer.addWidget(top_card)

        # ===== 表格卡片 =====
        table_card = QWidget()
        table_card.setObjectName("card")
        tv = QVBoxLayout(table_card)
        tv.setContentsMargins(10, 10, 10, 8)
        tv.setSpacing(6)

        # 表格
        self.model = TaskTableModel(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(34)
        header: QHeaderView = self.view.horizontalHeader()
        header.setSectionsMovable(True)                       # 列顺序可拖拽
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setSortIndicatorShown(True)                    # 排序箭头可视化
        header.setSortIndicatorClearable(True)
        header.sortIndicatorChanged.connect(self._on_sort_changed)
        header.sectionClicked.connect(self._on_header_clicked)
        header.sectionMoved.connect(self._on_column_moved)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_column_menu_at)
        self.view.doubleClicked.connect(lambda idx: self._on_double_click(idx))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)

        # 委托
        self._status_delegate = StatusDelegate(self.view)
        self._action_delegate = ActionDelegate(self.view)
        self._action_delegate.action.connect(self._on_action)
        self._rebind_delegates()
        tv.addWidget(self.view, 1)

        # 空数据提示（覆盖在表格视口上，不拦截鼠标）
        self.empty_hint = QLabel("暂无任务\n点击左上角『＋ 新建任务』开始添加",
                                 self.view.viewport())
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.view.viewport().installEventFilter(self)

        # 分页
        self.pager = PaginationBar()
        self.pager.page_changed.connect(self._on_page_changed)
        self.pager.page_size_changed.connect(self._on_page_size_changed)
        tv.addWidget(self.pager)
        outer.addWidget(table_card, 1)

    def eventFilter(self, obj, event):
        """表格视口尺寸变化时，让空状态提示始终铺满。"""
        from PyQt6.QtCore import QEvent
        if obj is self.view.viewport() and event.type() == QEvent.Type.Resize:
            self.empty_hint.setGeometry(self.view.viewport().rect())
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 状态持久化
    def _restore_states(self):
        # 注意：app_config.get() 内部已做 json 解析，这里直接得到 list/dict，
        # 切勿再次 json.loads（会抛 TypeError 被吞掉，导致委托不绑定/配置不恢复）。
        state = app_config.get(COL_STATE_KEY, "")
        if isinstance(state, list) and state:
            try:
                self._apply_column_state(state)
            except (ValueError, TypeError, KeyError, AttributeError):
                self._reset_columns()
        else:
            self._reset_columns()   # 首次启动应用默认列配置
        s = app_config.get("sort_state", "")
        if isinstance(s, dict) and s:
            self.sort_key = s.get("key", "created_at")
            self.sort_dir = s.get("dir", "desc")
            self._update_sort_indicator()

    def _save_states(self):
        state = self._column_state()
        app_config.set(COL_STATE_KEY, json.dumps(state, ensure_ascii=False))
        app_config.set("sort_state", json.dumps({"key": self.sort_key, "dir": self.sort_dir}))

    def _column_state(self):
        header: QHeaderView = self.view.horizontalHeader()
        state = []
        for logical in range(len(COLUMNS)):
            title = self.model.headerData(logical, Qt.Orientation.Horizontal)
            cid = self.model.column_ids[logical]
            state.append({
                "id": cid,
                "visible": not header.isSectionHidden(logical),
                "width": header.sectionSize(logical),
            })
        return state

    def _apply_column_state(self, state: list[dict]):
        """按保存的顺序/可见性/宽度应用列配置。"""
        ids = [s["id"] for s in state if s["id"] in {c[0] for c in COLUMNS}]
        for c in COLUMNS:
            if c[0] not in ids:
                ids.append(c[0])
        self.model.set_columns(ids)
        self._rebind_delegates()
        header: QHeaderView = self.view.horizontalHeader()
        for logical, cid in enumerate(ids):
            s = next((x for x in state if x["id"] == cid), None)
            if s is None:
                s = next(({"id": c[0], "visible": c[2], "width": c[3]} for c in COLUMNS
                          if c[0] == cid), {"visible": True, "width": 120})
            header.setSectionHidden(logical, not s.get("visible", True))
            header.resizeSection(logical, int(s.get("width", 120)))
        # 名称列弹性伸缩
        if ids and ids[0] == "name":
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

    def _rebind_delegates(self):
        for logical, cid in enumerate(self.model.column_ids):
            if cid == "status":
                self.view.setItemDelegateForColumn(logical, self._status_delegate)
            elif cid == "actions":
                self.view.setItemDelegateForColumn(logical, self._action_delegate)
            else:
                self.view.setItemDelegateForColumn(logical, None)

    # ------------------------------------------------------------------
    # 排序可视化
    def _on_header_clicked(self, logical: int):
        cid = self.model.column_ids[logical]
        sortable = {"name", "assignee", "deadline", "reminder_time", "status"}
        if cid not in sortable:
            return
        # 循环：升序 → 降序 → 默认
        if self.sort_key == cid:
            self.sort_dir = {"": "asc", "asc": "desc", "desc": ""}[self.sort_dir]
        else:
            self.sort_key, self.sort_dir = cid, "asc"
        self._update_sort_indicator()
        self._save_states()
        self.refresh()

    def _on_sort_changed(self, logical, order):
        """点击表头排序指示器（Qt 原生交互）同样生效。"""
        if logical < 0:
            # 指示器被清除 → 恢复默认（按创建时间，无方向）
            self.sort_key, self.sort_dir = "created_at", ""
            self._save_states()
            self.refresh()
            return
        cid = self.model.column_ids[logical]
        if cid in ("actions", "notes"):
            return
        self.sort_key = cid
        self.sort_dir = "asc" if order == Qt.SortOrder.AscendingOrder else "desc"
        self._save_states()
        self.refresh()

    def _update_sort_indicator(self):
        header: QHeaderView = self.view.horizontalHeader()
        if self.sort_dir == "":
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            return
        logical = self.model.column_ids.index(self.sort_key) if self.sort_key in self.model.column_ids else -1
        header.setSortIndicator(
            logical,
            Qt.SortOrder.AscendingOrder if self.sort_dir == "asc" else Qt.SortOrder.DescendingOrder,
        )

    def current_sort_text(self) -> str:
        titles = {c[0]: c[1] for c in COLUMNS}
        if self.sort_dir == "":
            return "默认（按创建时间）"
        arrow = "▲" if self.sort_dir == "asc" else "▼"
        return f"按 {titles.get(self.sort_key, self.sort_key)} {arrow} {'升序' if self.sort_dir == 'asc' else '降序'}"

    # ------------------------------------------------------------------
    # 列配置
    def _show_column_menu(self):
        self._show_column_menu_at(QCursor.pos())

    def _show_column_menu_at(self, pos):
        header: QHeaderView = self.view.horizontalHeader()
        menu = QMenu(self)
        for logical, cid in enumerate(self.model.column_ids):
            if cid == "actions":
                continue
            title = self.model.headerData(logical, Qt.Orientation.Horizontal)
            act = menu.addAction(title)
            act.setCheckable(True)
            act.setChecked(not header.isSectionHidden(logical))
            act.toggled.connect(lambda on, l=logical: self._toggle_column(l, on))
        menu.addSeparator()
        menu.addAction("重置列配置", self._reset_columns)
        menu.exec(pos)

    def _toggle_column(self, logical: int, visible: bool):
        self.view.horizontalHeader().setSectionHidden(logical, not visible)
        self._save_states()

    def _reset_columns(self):
        self.model.set_columns([c[0] for c in COLUMNS])
        self._rebind_delegates()
        header: QHeaderView = self.view.horizontalHeader()
        for logical, c in enumerate(COLUMNS):
            header.setSectionHidden(logical, not c[2])
            header.resizeSection(logical, c[3])
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._save_states()

    def _on_column_moved(self, logical: int, old_visual: int, new_visual: int):
        self._save_states()

    # ------------------------------------------------------------------
    # 数据刷新
    def refresh(self):
        criteria = self.search.criteria()
        tasks, total = repository.list_tasks(
            page=self.page_no, sort_key=self.sort_key if self.sort_dir else "created_at",
            sort_dir=self.sort_dir or "desc", criteria=criteria)
        self.model.set_tasks(tasks)
        self.pager.update_info(total, self.page_no,
                               self.pager.size or int(app_config.get("page_size", 200)))
        # 空数据提示
        self.empty_hint.setVisible(total == 0)
        if total == 0:
            self.empty_hint.setGeometry(self.view.viewport().rect())
            self.empty_hint.raise_()

    def _on_search_changed(self, _criteria):
        self.page_no = 1
        self.refresh()

    def _on_page_changed(self, p):
        self.page_no = p
        self.refresh()

    def _on_page_size_changed(self, n):
        app_config.set("page_size", n)
        self.page_no = 1
        self.refresh()

    # ------------------------------------------------------------------
    # 操作
    def on_new(self):
        dlg = TaskDialog(self)
        if dlg.exec() == 1:
            self.refresh()
            self.data_changed.emit()

    def _on_double_click(self, idx):
        if self.model.column_ids[idx.column()] == "actions":
            return
        self._edit(self.model.task_at(idx.row()))

    def on_edit_selected(self):
        rows = self.view.selectionModel().selectedRows()
        if rows:
            self._edit(self.model.task_at(rows[0].row()))

    def _edit(self, task: Task | None):
        if task is None:
            return
        if TaskDialog.edit(self, repository.get_task(task.id)):
            self.refresh()
            self.data_changed.emit()

    def on_delete_selected(self):
        rows = self.view.selectionModel().selectedRows()
        ids = [self.model.task_at(r.row()).id for r in rows if self.model.task_at(r.row())]
        if not ids:
            return
        if QMessageBox.question(self, "删除确认", f"确定删除选中的 {len(ids)} 个任务吗？删除后不可恢复。",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) != QMessageBox.StandardButton.Yes:
            return
        repository.delete_tasks(ids)
        self.refresh()
        self.data_changed.emit()

    def _on_action(self, task_id, action: str):
        if action == ACTION_EDIT:
            self._edit(repository.get_task(task_id))
        elif action == ACTION_DELETE:
            task = repository.get_task(task_id)
            if task and QMessageBox.question(
                    self, "删除确认", f"确定删除任务「{task.summary()}」吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    ) == QMessageBox.StandardButton.Yes:
                repository.delete_task(task_id)
                self.refresh()
                self.data_changed.emit()

    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("新建任务", self.on_new)
        menu.addAction("编辑", self.on_edit_selected)
        menu.addAction("删除", self.on_delete_selected)
        idx = self.view.indexAt(pos)
        if idx.isValid():
            task = self.model.task_at(idx.row())
            if task:
                status_menu = menu.addMenu("设为")
                for s in ("未开始", "进行中", "已完成"):
                    status_menu.addAction(s, lambda s=s, t=task: self._set_status(t, s))
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def _set_status(self, task: Task, status: str):
        repository.set_status(task.id, status)
        self.refresh()
        self.data_changed.emit()

    # ------------------------------------------------------------------
    # Excel 导入导出
    def selected_ids(self) -> list[int]:
        rows = self.view.selectionModel().selectedRows()
        return [self.model.task_at(r.row()).id for r in rows if self.model.task_at(r.row())]

    def on_export(self):
        n_selected = len(self.selected_ids())
        scope = self._ask_export_scope(n_selected)
        if scope is None:
            return
        if scope == "selected":
            tasks = repository.tasks_by_ids(self.selected_ids())
        elif scope == "filtered":
            tasks, total = repository.list_tasks(
                page=1, page_size=10 ** 9,
                sort_key=self.sort_key if self.sort_dir else "created_at",
                sort_dir=self.sort_dir or "desc", criteria=self.search.criteria())
        else:
            tasks = repository.all_tasks()
        if not tasks:
            QMessageBox.information(self, "导出 Excel", "没有可导出的任务。")
            return
        default_name = f"任务导出_{__import__('datetime').datetime.now():%Y%m%d_%H%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出 Excel", default_name,
                                              "Excel 工作簿 (*.xlsx)")
        if not path:
            return
        n = excel_io.export_tasks(path, tasks)
        QMessageBox.information(self, "导出 Excel", f"已导出 {n} 条任务到：\n{path}")

    def _ask_export_scope(self, n_selected: int) -> str | None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QRadioButton, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("选择导出范围")
        v = QVBoxLayout(dlg)
        rb_all = QRadioButton("全部任务")
        rb_sel = QRadioButton(f"选中的任务（{n_selected} 条）")
        rb_fil = QRadioButton("当前筛选结果")
        rb_all.setChecked(True)
        rb_sel.setEnabled(n_selected > 0)
        v.addWidget(rb_all)
        v.addWidget(rb_sel)
        v.addWidget(rb_fil)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != 1:
            return None
        if rb_sel.isChecked():
            return "selected"
        if rb_fil.isChecked():
            return "filtered"
        return "all"

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入 Excel", "", "Excel 工作簿 (*.xlsx)")
        if not path:
            return
        # 冲突策略选择
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QRadioButton, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("导入选项")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("遇到重复任务（名称+执行人+截止时间相同）时："))
        rb_skip = QRadioButton("跳过重复任务")
        rb_over = QRadioButton("覆盖重复任务")
        rb_skip.setChecked(True)
        v.addWidget(rb_skip)
        v.addWidget(rb_over)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != 1:
            return
        report = excel_io.import_tasks(path, strategy="overwrite" if rb_over.isChecked() else "skip")
        QMessageBox.information(self, "导入完成", report.summary())
        self.page_no = 1
        self.refresh()
        self.data_changed.emit()
