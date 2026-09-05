"""应用配置：基于 user_settings 表的持久化设置。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import db

# 默认值
DEFAULTS = {
    "theme": "light",                # light / dark
    "font_size": 13,
    "poll_interval": 5,              # 秒（1-60）
    "sound_enabled": True,
    "sound_file": "",                # 空 = 使用内置 chime
    "page_size": 200,
    "sort_state": "",                # json: {"key": "deadline", "dir": "asc"}
    "column_state": "",              # json: [{id, visible, width}...]（顺序即列顺序）
    "window_state": "",              # json: {x, y, w, h, maximized}
    "tray_close": True,              # 关闭时最小化到托盘
    "first_run_done": False,
}

_ASSETS_DIR = Path(__file__).parent / "assets"


def assets_dir() -> Path:
    """内置资源目录（PyInstaller 打包后为 sys._MEIPASS/assets）。"""
    import sys
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        p = Path(bundled) / "assets"
        if p.exists():
            return p
    return _ASSETS_DIR


def get(key: str, default: Any = None) -> Any:
    raw = _raw(key)
    if raw is None:
        return DEFAULTS.get(key, default)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def _raw(key: str):
    row = db.get_conn().execute("SELECT value FROM user_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set(key: str, value: Any) -> None:
    raw = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    db.get_conn().execute(
        "INSERT INTO user_settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, raw),
    )
    db.get_conn().commit()


def default_sound() -> str:
    return str(assets_dir() / "chime.wav")


def built_in_sounds() -> list[tuple[str, str]]:
    """内置 3 种音效：(显示名, 路径)。"""
    base = assets_dir()
    return [
        ("清脆铃声", str(base / "chime.wav")),
        ("叮咚提示", str(base / "ding.wav")),
        ("紧急警报", str(base / "alert.wav")),
    ]
