"""声音播放：QSoundEffect 播放 wav，失败回退 winsound。"""
from __future__ import annotations

from pathlib import Path

from . import app_config


class SoundPlayer:
    """播放提醒音效。"""

    def __init__(self):
        self._effect = None      # QSoundEffect 懒创建（需 QApplication）
        self._played_path = ""

    def play(self, path: str = "", enabled: bool = True) -> bool:
        """播放指定音效；返回是否成功。"""
        if not enabled:
            return False
        path = path or app_config.get("sound_file", "") or app_config.default_sound()
        if not path or not Path(path).exists():
            path = app_config.default_sound()
        if not Path(path).exists():
            return self._fallback()
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QSoundEffect
            if self._effect is None or self._played_path != path:
                self._effect = QSoundEffect()
                self._effect.setSource(QUrl.fromLocalFile(path))
                self._effect.setVolume(0.9)
                self._played_path = path
            self._effect.play()
            return True
        except Exception:
            return self._fallback()

    @staticmethod
    def _fallback() -> bool:
        """系统蜂鸣回退。"""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return True
        except Exception:
            return False
