"""设置页：外观 / 提醒 / 行为 / 数据管理。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
                             QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from .. import app_config, backup, db
from .theme import apply_theme
from .widgets import confirm

THEME_NAMES = {"light": "浅色主题", "dark": "深色主题"}


class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str, int)
    behavior_changed = pyqtSignal()
    data_restored = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._load()
        self._connect()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(10)

        title = QLabel("设置")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # 外观
        g_look = QGroupBox("外观")
        h = QHBoxLayout(g_look)
        h.addWidget(QLabel("主题："))
        self.cmb_theme = QComboBox()
        for k, v in THEME_NAMES.items():
            self.cmb_theme.addItem(v, k)
        h.addWidget(self.cmb_theme)
        h.addWidget(QLabel("字号："))
        self.spin_font = QSpinBox()
        self.spin_font.setRange(11, 22)
        h.addWidget(self.spin_font)
        h.addWidget(QLabel("px"))
        h.addStretch(1)
        layout.addWidget(g_look)

        # 提醒
        g_alert = QGroupBox("提醒")
        h2 = QHBoxLayout(g_alert)
        h2.addWidget(QLabel("轮询间隔："))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setSuffix(" 秒")
        h2.addWidget(self.spin_interval)
        self.chk_sound = QCheckBox("启用声音")
        h2.addWidget(self.chk_sound)
        h2.addWidget(QLabel("音效："))
        self.cmb_sound = QComboBox()
        for name, path in app_config.built_in_sounds():
            self.cmb_sound.addItem(name, path)
        self.cmb_sound.addItem("自定义…", "")
        h2.addWidget(self.cmb_sound, 1)
        self.btn_sound_pick = QPushButton("浏览")
        self.btn_test = QPushButton("试听")
        self.btn_sound_pick.clicked.connect(self._pick_sound)
        self.btn_test.clicked.connect(self._test_sound)
        h2.addWidget(self.btn_sound_pick)
        h2.addWidget(self.btn_test)
        h2.addStretch(1)
        layout.addWidget(g_alert)

        # 行为
        g_beh = QGroupBox("行为")
        h3 = QHBoxLayout(g_beh)
        self.chk_tray_close = QCheckBox("关闭窗口时最小化到托盘（不退出）")
        h3.addWidget(self.chk_tray_close)
        h3.addStretch(1)
        h3.addWidget(QLabel("每页条数："))
        self.cmb_page_size = QComboBox()
        for n in (50, 100, 200, 500):
            self.cmb_page_size.addItem(str(n), n)
        h3.addWidget(self.cmb_page_size)
        layout.addWidget(g_beh)

        # 数据管理
        g_data = QGroupBox("数据管理")
        v = QVBoxLayout(g_data)
        row1 = QHBoxLayout()
        btn_backup = QPushButton("备份（JSON）")
        btn_restore = QPushButton("恢复（JSON）")
        btn_open_dir = QPushButton("打开数据目录")
        btn_backup.setObjectName("btnRow")
        btn_restore.setObjectName("btnRow")
        btn_open_dir.setObjectName("btnRow")
        btn_backup.clicked.connect(self._backup)
        btn_restore.clicked.connect(self._restore)
        btn_open_dir.clicked.connect(self._open_dir)
        row1.addWidget(btn_backup)
        row1.addWidget(btn_restore)
        row1.addWidget(btn_open_dir)
        row1.addStretch(1)
        v.addLayout(row1)
        db_lbl = QLabel(f"数据库文件：{db.db_path()}")
        db_lbl.setObjectName("tagNote")
        db_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(db_lbl)
        layout.addWidget(g_data)

        layout.addStretch(1)

    def _connect(self):
        # 信号在 _load() 之后连接，避免加载过程把默认值写回数据库
        self.cmb_theme.currentIndexChanged.connect(self._apply)
        self.spin_font.valueChanged.connect(self._apply)
        self.spin_interval.valueChanged.connect(self._save)
        self.chk_sound.stateChanged.connect(self._save)
        self.chk_tray_close.stateChanged.connect(self._save)
        self.cmb_page_size.currentIndexChanged.connect(self._save)
        self.cmb_sound.activated.connect(self._on_sound_selected)

    # ------------------------------------------------------------------
    def _load(self):
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(app_config.get("theme"))))
        self.spin_font.setValue(int(app_config.get("font_size", 13)))
        self.spin_interval.setValue(int(app_config.get("poll_interval", 5)))
        self.chk_sound.setChecked(bool(app_config.get("sound_enabled", True)))
        self.chk_tray_close.setChecked(bool(app_config.get("tray_close", True)))
        size = int(app_config.get("page_size", 200))
        idx = self.cmb_page_size.findData(size)
        self.cmb_page_size.setCurrentIndex(idx if idx >= 0 else 2)
        sound_file = app_config.get("sound_file", "")
        if sound_file:
            self.cmb_sound.addItem(f"自定义：{sound_file}", sound_file)
            self.cmb_sound.setCurrentIndex(self.cmb_sound.count() - 1)

    def _save(self):
        app_config.set("poll_interval", self.spin_interval.value())
        app_config.set("sound_enabled", self.chk_sound.isChecked())
        app_config.set("tray_close", self.chk_tray_close.isChecked())
        app_config.set("page_size", self.cmb_page_size.currentData())
        # 通知主窗口立即应用（轮询间隔/每页条数），无需重启
        self.behavior_changed.emit()

    def _apply(self):
        theme = self.cmb_theme.currentData() or "light"
        font = self.spin_font.value()
        app_config.set("theme", theme)
        app_config.set("font_size", font)
        self.theme_changed.emit(theme, font)

    def _pick_sound(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择音效文件", "",
                                              "音频文件 (*.wav)")
        if not path:
            return
        app_config.set("sound_file", path)
        # 只保留一个自定义项：先移除旧项再追加，避免多次浏览后下拉框堆积
        for i in range(self.cmb_sound.count()):
            if self.cmb_sound.itemText(i).startswith("自定义："):
                self.cmb_sound.removeItem(i)
                break
        self.cmb_sound.addItem(f"自定义：{path}", path)
        self.cmb_sound.setCurrentIndex(self.cmb_sound.count() - 1)
        self._save_sound()

    def _on_sound_selected(self):
        self._save_sound()
        self._test_sound()

    def _save_sound(self):
        data = self.cmb_sound.currentData()
        app_config.set("sound_file", data or "")

    def _test_sound(self):
        from ..sound import SoundPlayer
        data = self.cmb_sound.currentData()
        SoundPlayer().play(path=data or "", enabled=True)

    def _backup(self):
        default = f"任务备份_{__import__('datetime').datetime.now():%Y%m%d_%H%M}.json"
        path, _ = QFileDialog.getSaveFileName(self, "备份数据", default, "JSON (*.json)")
        if not path:
            return
        n = backup.export_json(path)
        QMessageBox.information(self, "备份完成", f"已备份 {n} 条任务（含提醒历史）到：\n{path}")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "恢复数据", "", "JSON (*.json)")
        if not path:
            return
        if not confirm(self, "恢复数据",
                       "恢复将按编号覆盖现有任务与提醒历史中相同编号的记录。\n"
                       "建议先执行一次备份，确定要继续吗？"):
            return
        try:
            n_tasks, n_hist = backup.import_json(path)
        except Exception as e:
            QMessageBox.warning(self, "恢复失败", f"备份文件无效：{e}")
            return
        QMessageBox.information(self, "恢复完成", f"已导入 {n_tasks} 条任务、{n_hist} 条提醒历史。")
        # 通知各页面立即刷新恢复后的数据
        self.data_restored.emit()

    def _open_dir(self):
        import os
        import subprocess
        path = db.db_path()
        os.makedirs(path if os.path.isdir(path) else __import__("pathlib").Path(path).parent,
                    exist_ok=True)
        subprocess.Popen(["explorer", "/select,", path])
