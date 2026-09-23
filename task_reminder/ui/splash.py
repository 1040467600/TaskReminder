"""启动画面：程序化绘制的警务风格 splash（深蓝渐变 + 金色警徽星形，无外部图片依赖）。"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import QApplication, QSplashScreen

from .. import APP_NAME, __version__


def _star(cx: float, cy: float, r_out: float, r_in: float) -> QPolygonF:
    """五角星顶点（尖角朝上）。"""
    pts = QPolygonF()
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 2 + i * math.pi / 5
        pts.append(QPointF(cx + r * math.cos(a), cy - r * math.sin(a)))
    return pts


def create_pixmap(width: int = 560, height: int = 360, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(width * dpr), int(height * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    W, H = width, height

    # 圆角裁剪
    frame = QPainterPath()
    frame.addRoundedRect(0.0, 0.0, float(W), float(H), 18.0, 18.0)
    p.setClipPath(frame)

    # 深蓝渐变背景
    bg = QLinearGradient(0.0, 0.0, float(W), float(H))
    bg.setColorAt(0.0, QColor("#0C2D6B"))
    bg.setColorAt(0.55, QColor("#143E8F"))
    bg.setColorAt(1.0, QColor("#0A1F4D"))
    p.fillPath(frame, bg)

    # 右上柔光
    glow = QRadialGradient(float(W) * 0.85, -40.0, 320.0)
    glow.setColorAt(0.0, QColor(255, 255, 255, 36))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(0, 0, W, H, glow)

    # 底部光带
    band = QLinearGradient(0.0, float(H) - 120, 0.0, float(H))
    band.setColorAt(0.0, QColor(245, 197, 66, 0))
    band.setColorAt(1.0, QColor(245, 197, 66, 26))
    p.fillRect(0, H - 120, W, 120, band)

    # 警徽：金色双环 + 五角星 + 底部缎带弧
    cx, cy = W / 2, 118
    p.setPen(QPen(QColor("#F5C542"), 3))
    p.setBrush(QColor(10, 31, 77, 200))
    p.drawEllipse(QPointF(cx, cy), 52.0, 52.0)
    p.setPen(QPen(QColor(245, 197, 66, 140), 1.5))
    p.drawEllipse(QPointF(cx, cy), 44.0, 44.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#F5C542"))
    p.drawPolygon(_star(cx, cy - 2, 30.0, 12.0))

    # 主标题 + 版本号
    p.setPen(QColor("#FFFFFF"))
    f_title = QFont("Microsoft YaHei", 23)
    f_title.setBold(True)
    p.setFont(f_title)
    p.drawText(0, 190, W, 44, Qt.AlignmentFlag.AlignCenter, APP_NAME)

    f_ver = QFont("Microsoft YaHei", 11)
    p.setFont(f_ver)
    p.setPen(QColor(245, 197, 66, 230))
    p.drawText(0, 238, W, 24, Qt.AlignmentFlag.AlignCenter, f"v{__version__}")

    # 金色分隔线 + 加载提示
    p.setPen(QPen(QColor(245, 197, 66, 90), 1))
    p.drawLine(int(W * 0.18), 276, int(W * 0.82), 276)
    p.setPen(QColor(255, 255, 255, 170))
    f_tip = QFont("Microsoft YaHei", 9)
    p.setFont(f_tip)
    p.drawText(0, 288, W, 24, Qt.AlignmentFlag.AlignCenter, "正在启动，请稍候…")

    p.end()
    return pm


def show_splash() -> QSplashScreen:
    splash = QSplashScreen(create_pixmap())
    splash.setWindowFlags(Qt.WindowType.FramelessWindowHint
                          | Qt.WindowType.WindowStaysOnTopHint
                          | Qt.WindowType.SplashScreen)
    # 居中于主屏
    screen = QApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        splash.move(geo.center() - splash.rect().center())
    splash.show()
    QApplication.processEvents()
    return splash
