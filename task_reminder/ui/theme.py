"""主题样式：浅色 / 深色两套现代化 QSS，支持字号缩放。"""
from __future__ import annotations

_LIGHT = """
* { font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif; }
QWidget { background: #F5F7FA; color: #1F2937; font-size: {FS}px; }
QMainWindow, QDialog { background: #F5F7FA; }

/* 侧边栏 */
#sidebar { background: #1E293B; border: none; }
#sidebar QLabel { color: #E2E8F0; background: transparent; }
#appTitle { font-size: {FS_T}px; font-weight: 600; color: #FFFFFF; background: transparent; padding: 2px 4px; }
#appVersion { color: #94A3B8; font-size: {FS_S}px; padding: 8px; background: transparent; }
QPushButton#navBtn {
    color: #CBD5E1; background: transparent; border: none; border-radius: 8px;
    padding: 11px 14px; text-align: left; font-size: {FS}px;
}
QPushButton#navBtn:hover { background: #334155; color: #FFFFFF; }
QPushButton#navBtn:checked { background: #2563EB; color: #FFFFFF; font-weight: 600; }

/* 页面头部与卡片 */
#pageTitle { font-size: {FS_T}px; font-weight: 600; }
#card { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; }
#card QLabel { background: transparent; }
QFrame#vsep { background: #E2E8F0; border: none; max-width: 1px; min-width: 1px; margin: 2px 4px; }
#emptyHint { background: transparent; color: #9CA3AF; font-size: {FS_T}px; }
#cardTitle { color: #6B7280; font-size: {FS_S}px; }
#cardValue { font-size: {FS_XT}px; font-weight: 700; }
QLabel#cardValue[themeColor="blue"] { color: #2563EB; }
QLabel#cardValue[themeColor="green"] { color: #16A34A; }
QLabel#cardValue[themeColor="gray"] { color: #64748B; }
QLabel#cardValue[themeColor="red"] { color: #DC2626; }
QLabel#cardValue[themeColor="amber"] { color: #D97706; }

/* 表格 */
QTableView, QTableWidget {
    background: #FFFFFF; alternate-background-color: #F8FAFC;
    border: 1px solid #E5E7EB; border-radius: 8px; gridline-color: #EEF1F5;
    selection-background-color: #DBEAFE; selection-color: #1E293B;
}
QHeaderView::section {
    background: #F1F5F9; color: #475569; padding: 8px; border: none;
    border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; font-weight: 600;
}
QTableView QTableCornerButton::section { background: #F1F5F9; border: none; }

/* 输入控件 */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit {
    background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 8px;
    selection-background-color: #2563EB; selection-color: #FFFFFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus { border-color: #2563EB; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #FFFFFF; border: 1px solid #E5E7EB; }

/* 复选框 / 单选钮指示器（必须显式定义 ::indicator，否则样式表命中后原生圆圈/方框不再绘制） */
QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; background: #FFFFFF; border: 1.5px solid #9CA3AF;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; border-width: 2px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #2563EB; }
QCheckBox::indicator:checked {
    background: #2563EB; border-color: #2563EB; image: url({CHECK_PNG});
}
QRadioButton::indicator:checked {
    border-color: #2563EB;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #2563EB, stop:0.32 #2563EB, stop:0.46 #FFFFFF, stop:1 #FFFFFF);
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    border-color: #D1D5DB; background: #F9FAFB;
}

/* 按钮 */
QPushButton {
    background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px;
    padding: 6px 14px; color: #374151;
}
QPushButton:hover { background: #F3F4F6; border-color: #9CA3AF; }
QPushButton:pressed { background: #E5E7EB; }
QPushButton:disabled { color: #9CA3AF; background: #F9FAFB; }
QPushButton#btnPrimary { background: #2563EB; border-color: #2563EB; color: #FFFFFF; font-weight: 600; }
QPushButton#btnPrimary:hover { background: #1D4ED8; }
QPushButton#btnSuccess { background: #16A34A; border-color: #16A34A; color: #FFFFFF; font-weight: 600; }
QPushButton#btnSuccess:hover { background: #15803D; }
QPushButton#btnDanger { background: #FFFFFF; border-color: #FCA5A5; color: #DC2626; }
QPushButton#btnDanger:hover { background: #FEF2F2; }
QPushButton#btnGhost { border: none; background: transparent; color: #2563EB; padding: 4px 8px; }
QPushButton#btnGhost:hover { background: #EFF6FF; border-radius: 6px; }
QPushButton#btnRow { padding: 2px 10px; font-size: {FS_S}px; border-radius: 5px; }

/* 滚动条 */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C7CDD6; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9CA3AF; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #C7CDD6; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

/* 其他 */
QGroupBox { border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 12px; background: #FFFFFF; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #374151; }
QStatusBar { background: #EEF1F5; color: #64748B; }
QToolTip { background: #1E293B; color: #FFFFFF; border: none; padding: 6px; }
#reminderTitle { font-size: {FS_T}px; font-weight: 700; color: #2563EB; }
#tagNote { color: #6B7280; font-size: {FS_S}px; }
QListWidget { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; }
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #DBEAFE; color: #1E293B; }
"""

_DARK = """
* { font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif; }
QWidget { background: #0F172A; color: #E2E8F0; font-size: {FS}px; }
QMainWindow, QDialog { background: #0F172A; }

#sidebar { background: #1E293B; border: none; }
#sidebar QLabel { color: #E2E8F0; background: transparent; }
#appTitle { font-size: {FS_T}px; font-weight: 600; color: #FFFFFF; background: transparent; padding: 2px 4px; }
#appVersion { color: #94A3B8; font-size: {FS_S}px; padding: 8px; background: transparent; }
QPushButton#navBtn {
    color: #CBD5E1; background: transparent; border: none; border-radius: 8px;
    padding: 11px 14px; text-align: left; font-size: {FS}px;
}
QPushButton#navBtn:hover { background: #334155; color: #FFFFFF; }
QPushButton#navBtn:checked { background: #3B82F6; color: #FFFFFF; font-weight: 600; }

#pageTitle { font-size: {FS_T}px; font-weight: 600; }
#card { background: #1E293B; border: 1px solid #334155; border-radius: 10px; }
#card QLabel { background: transparent; }
QFrame#vsep { background: #334155; border: none; max-width: 1px; min-width: 1px; margin: 2px 4px; }
#emptyHint { background: transparent; color: #64748B; font-size: {FS_T}px; }
#cardTitle { color: #94A3B8; font-size: {FS_S}px; }
#cardValue { font-size: {FS_XT}px; font-weight: 700; }
QLabel#cardValue[themeColor="blue"] { color: #60A5FA; }
QLabel#cardValue[themeColor="green"] { color: #4ADE80; }
QLabel#cardValue[themeColor="gray"] { color: #94A3B8; }
QLabel#cardValue[themeColor="red"] { color: #F87171; }
QLabel#cardValue[themeColor="amber"] { color: #FBBF24; }

QTableView, QTableWidget {
    background: #1E293B; alternate-background-color: #172033;
    border: 1px solid #334155; border-radius: 8px; gridline-color: #2C3A4F;
    selection-background-color: #1E3A8A; selection-color: #E2E8F0;
}
QHeaderView::section {
    background: #16202F; color: #94A3B8; padding: 8px; border: none;
    border-right: 1px solid #2C3A4F; border-bottom: 1px solid #2C3A4F; font-weight: 600;
}
QTableView QTableCornerButton::section { background: #16202F; border: none; }

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit {
    background: #16202F; border: 1px solid #334155; border-radius: 6px; padding: 6px 8px;
    color: #E2E8F0; selection-background-color: #2563EB; selection-color: #FFFFFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus { border-color: #3B82F6; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1E293B; border: 1px solid #334155; color: #E2E8F0; }

/* 复选框 / 单选钮指示器 */
QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; background: #16202F; border: 1.5px solid #4C5F7A;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; border-width: 2px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #60A5FA; }
QCheckBox::indicator:checked {
    background: #2563EB; border-color: #2563EB; image: url({CHECK_PNG});
}
QRadioButton::indicator:checked {
    border-color: #60A5FA;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #60A5FA, stop:0.32 #60A5FA, stop:0.46 #16202F, stop:1 #16202F);
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    border-color: #3B4A5F; background: #1B2432;
}

QPushButton {
    background: #263244; border: 1px solid #3B4A5F; border-radius: 6px;
    padding: 6px 14px; color: #E2E8F0;
}
QPushButton:hover { background: #31405A; border-color: #4C5F7A; }
QPushButton:pressed { background: #1B2432; }
QPushButton:disabled { color: #64748B; background: #1B2432; }
QPushButton#btnPrimary { background: #2563EB; border-color: #2563EB; color: #FFFFFF; font-weight: 600; }
QPushButton#btnPrimary:hover { background: #3B82F6; }
QPushButton#btnSuccess { background: #16A34A; border-color: #16A34A; color: #FFFFFF; font-weight: 600; }
QPushButton#btnSuccess:hover { background: #22C55E; }
QPushButton#btnDanger { background: transparent; border-color: #7F1D1D; color: #F87171; }
QPushButton#btnDanger:hover { background: #450A0A; }
QPushButton#btnGhost { border: none; background: transparent; color: #60A5FA; padding: 4px 8px; }
QPushButton#btnGhost:hover { background: #16202F; border-radius: 6px; }
QPushButton#btnRow { padding: 2px 10px; font-size: {FS_S}px; border-radius: 5px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3B4A5F; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4C5F7A; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #3B4A5F; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

QGroupBox { border: 1px solid #334155; border-radius: 8px; margin-top: 12px; background: #1E293B; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #CBD5E1; }
QStatusBar { background: #16202F; color: #94A3B8; }
QToolTip { background: #E2E8F0; color: #0F172A; border: none; padding: 6px; }
#reminderTitle { font-size: {FS_T}px; font-weight: 700; color: #60A5FA; }
#tagNote { color: #94A3B8; font-size: {FS_S}px; }
QListWidget { background: #1E293B; border: 1px solid #334155; border-radius: 8px; }
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #1E3A8A; color: #FFFFFF; }
"""


def theme_qss(theme: str = "light", font_size: int = 13) -> str:
    """生成当前主题的 QSS（按字号缩放派生字号）。"""
    from .. import app_config
    tpl = _LIGHT if theme == "light" else _DARK
    fs = max(11, min(22, int(font_size)))
    check_png = (app_config.assets_dir() / "check.png").as_posix()
    return tpl.replace("{FS}", str(fs)) \
              .replace("{FS_S}", str(fs - 2)) \
              .replace("{FS_T}", str(fs + 3)) \
              .replace("{FS_XT}", str(fs + 8)) \
              .replace("{CHECK_PNG}", check_png)


def apply_theme(app, theme: str = "light", font_size: int = 13) -> None:
    from PyQt6.QtGui import QFont
    app.setFont(QFont("Microsoft YaHei UI", font_size))
    app.setStyleSheet(theme_qss(theme, font_size))
