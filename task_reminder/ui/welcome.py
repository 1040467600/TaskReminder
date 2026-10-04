"""进入界面：警务风格欢迎窗口，点击「进入系统」后进入主界面。"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from .. import APP_NAME, __version__


def _star(cx: float, cy: float, r_out: float, r_in: float) -> QPolygonF:
    """五角星顶点（尖角朝上）。"""
    pts = QPolygonF()
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 2 + i * math.pi / 5
        pts.append(QPointF(cx + r * math.cos(a), cy - r * math.sin(a)))
    return pts


class WelcomeWindow(QWidget):
    """无边框欢迎页：品牌画面 + 系统全称 + 「进入系统」按钮。"""

    entered = pyqtSignal()

    W, H = 620, 430

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self._drag_pos = None
        self._build()
        self._center()

    # ------------------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # 顶部留白（警徽由 paintEvent 直接绘制）
        outer.addSpacing(205)

        title = QLabel("彭城派出所")
        title.setObjectName("welcomeTitle1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        title2 = QLabel("任务闭环管理系统")
        title2.setObjectName("welcomeTitle2")
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title2)

        ver = QLabel(f"v{__version__}")
        ver.setObjectName("welcomeVersion")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(ver)

        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_enter = QPushButton("进 入 系 统")
        self.btn_enter.setObjectName("btnEnter")
        self.btn_enter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enter.setFixedSize(180, 42)
        self.btn_enter.clicked.connect(self.entered.emit)
        row.addWidget(self.btn_enter)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addSpacing(34)

        # 欢迎页专属样式（不依赖全局主题，深色背景自洽）
        self.setStyleSheet(
            """
            QLabel#welcomeTitle1 {
                color: #F5C542; background: transparent;
                font-family: 'Microsoft YaHei'; font-size: 30px; font-weight: 700;
                letter-spacing: 6px;
            }
            QLabel#welcomeTitle2 {
                color: #FFFFFF; background: transparent;
                font-family: 'Microsoft YaHei'; font-size: 21px; font-weight: 600;
                letter-spacing: 4px;
            }
            QLabel#welcomeVersion {
                color: rgba(255,255,255,150); background: transparent;
                font-family: 'Microsoft YaHei'; font-size: 12px;
                padding-top: 8px;
            }
            QPushButton#btnEnter {
                color: #0C2D6B; background: #F5C542;
                border: none; border-radius: 21px;
                font-family: 'Microsoft YaHei'; font-size: 16px; font-weight: 700;
                letter-spacing: 2px;
            }
            QPushButton#btnEnter:hover { background: #FFD65E; }
            QPushButton#btnEnter:pressed { background: #E0AE2E; }
            """
        )

    def _center(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center() - self.rect().center())

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 注意：offscreen 平台插件在半透明窗口上描边圆角矩形会硬崩溃，
        # 外框金线用"金底圆角 + 内缩背景圆角"两层填充实现，不用 drawRoundedRect 描边。
        frame = QPainterPath()
        frame.addRoundedRect(0.0, 0.0, float(self.W), float(self.H), 18.0, 18.0)
        p.fillPath(frame, QColor(245, 197, 66, 90))

        inner = QPainterPath()
        inner.addRoundedRect(1.5, 1.5, float(self.W - 3), float(self.H - 3), 16.0, 16.0)
        bg = QLinearGradient(0.0, 0.0, float(self.W), float(self.H))
        bg.setColorAt(0.0, QColor("#0C2D6B"))
        bg.setColorAt(0.55, QColor("#143E8F"))
        bg.setColorAt(1.0, QColor("#0A1F4D"))
        p.fillPath(inner, bg)
        p.setClipPath(inner)

        glow = QRadialGradient(float(self.W) * 0.85, -40.0, 360.0)
        glow.setColorAt(0.0, QColor(255, 255, 255, 36))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(0, 0, self.W, self.H, glow)

        band = QLinearGradient(0.0, float(self.H) - 150, 0.0, float(self.H))
        band.setColorAt(0.0, QColor(245, 197, 66, 0))
        band.setColorAt(1.0, QColor(245, 197, 66, 24))
        p.fillRect(0, self.H - 150, self.W, 150, band)

        # 警徽：金色双环 + 五角星
        cx = self.W / 2
        cy = 92.0
        p.setPen(QPen(QColor("#F5C542"), 3))
        p.setBrush(QColor(10, 31, 77, 200))
        p.drawEllipse(QPointF(cx, cy), 50.0, 50.0)
        p.setPen(QPen(QColor(245, 197, 66, 140), 1.5))
        p.setBrush(QColor(20, 62, 143, 180))
        p.drawEllipse(QPointF(cx, cy), 42.0, 42.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F5C542"))
        p.drawPolygon(_star(cx, cy - 2, 29.0, 11.5))
        p.end()

    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        # 回车/空格也可进入；Esc 直接退出应用
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.entered.emit()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def sizeHint(self) -> QSize:
        return QSize(self.W, self.H)
