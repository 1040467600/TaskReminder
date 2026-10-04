"""v2.4.0 进入界面（WelcomeWindow）测试。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


def test_welcome_enter_signal(qtbot):
    from task_reminder.ui.welcome import WelcomeWindow
    w = WelcomeWindow()
    qtbot.addWidget(w)
    fired = []
    w.entered.connect(lambda: fired.append(1))
    w.btn_enter.click()
    assert fired == [1]


def test_welcome_title_texts(qtbot):
    from task_reminder.ui.welcome import WelcomeWindow
    w = WelcomeWindow()
    qtbot.addWidget(w)
    t1 = w.findChild(QLabel, "welcomeTitle1")
    t2 = w.findChild(QLabel, "welcomeTitle2")
    assert t1.text() == "彭城派出所"
    assert t2.text() == "任务闭环管理系统"
    assert "2.4.0" in w.findChild(QLabel, "welcomeVersion").text()


def test_welcome_enter_key(qtbot):
    from task_reminder.ui.welcome import WelcomeWindow
    w = WelcomeWindow()
    qtbot.addWidget(w)
    fired = []
    w.entered.connect(lambda: fired.append(1))
    qtbot.keyClick(w, Qt.Key.Key_Return)
    assert fired == [1]


def test_welcome_esc_closes(qtbot):
    from task_reminder.ui.welcome import WelcomeWindow
    w = WelcomeWindow()
    qtbot.addWidget(w)
    w.show()
    qtbot.keyClick(w, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=2000)


def test_main_window_brand_title_no_icon(qtbot):
    """侧边栏只显示品牌名两行，不再有铃铛图标标题。"""
    from task_reminder.ui.main_window import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    b1 = win.findChild(QLabel, "appBrand1")
    b2 = win.findChild(QLabel, "appBrand2")
    assert b1 is not None and b1.text() == "彭城派出所"
    assert b2 is not None and b2.text() == "任务闭环管理系统"
    assert win.findChild(QLabel, "appTitle") is None
    assert win.windowTitle().startswith("彭城派出所任务闭环管理系统")
