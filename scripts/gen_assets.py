"""生成应用资源：app.ico 图标与 3 个内置提示音 wav。

纯标准库实现（无 PIL 依赖）：
- app.ico: 多尺寸 PNG-in-ICO？为兼容性采用 BMP 帧格式（32bpp BGRA）。
- wav: 16-bit PCM 单声道 22050Hz。
"""
from __future__ import annotations

import math
import shutil
import struct
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "task_reminder" / "assets"


# ---------------------------------------------------------------------------
# ICO 生成
def _draw_icon(size: int) -> bytes:
    """绘制图标帧：蓝色渐变圆角方块 + 白色铃铛，返回 32bpp BGRA 像素数据。"""
    px = bytearray(size * size * 4)
    cx = cy = (size - 1) / 2
    r_rect = size * 0.44          # 圆角半径
    half = size * 0.46
    bell_r = size * 0.26
    for y in range(size):
        for x in range(size):
            # 圆角方块判定
            dx = max(abs(x - cx) - (half - r_rect), 0)
            dy = max(abs(y - cy) - (half - r_rect), 0)
            inside = (dx * dx + dy * dy) <= r_rect * r_rect
            if not inside:
                continue
            idx = (y * size + x) * 4
            # 对角渐变：#2563EB → #1E40AF
            t = (x + y) / (2 * size)
            r = int(0x25 + (0x1E - 0x25) * t)
            g = int(0x63 + (0x40 - 0x63) * t)
            b = int(0xEB + (0xAF - 0xEB) * t)
            # 铃铛（圆顶 + 底部横条）
            ddx, ddy = x - cx, y - cy * 0.92
            d = math.hypot(ddx, ddy * 1.15)
            if d < bell_r:
                shade = max(0.0, min(1.0, 1.0 - 0.18 * (ddy / bell_r if ddy else 0)))
                r = g = b = int(255 * shade)
            px[idx:idx + 4] = bytes((b, g, r, 255))
    return bytes(px)


def _bmp_frame(size: int, pixels: bytes) -> bytes:
    """单帧 BITMAPINFOHEADER + 像素 + AND 掩码。"""
    header = struct.pack(
        "<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
        len(pixels), 0, 0, 0, 0,
    )
    # 像素自下而上
    rows = []
    row_len = size * 4
    for y in range(size - 1, -1, -1):
        rows.append(pixels[y * row_len:(y + 1) * row_len])
    bottom_up = b"".join(rows)
    mask_row = ((size + 31) // 32) * 4
    and_mask = b"\x00" * (mask_row * size)
    return header + bottom_up + and_mask


def build_icon(path: Path):
    frames = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        frames.append((size, _bmp_frame(size, _draw_icon(size))))
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = b""
    body = b""
    for size, data in frames:
        w = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        body += data
        offset += len(data)
    path.write_bytes(header + entries + body)
    print(f"icon: {path} ({path.stat().st_size} bytes)")


# ---------------------------------------------------------------------------
# 提示音合成
def _write_wav(path: Path, samples: list[float]):
    pcm = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(pcm)
    print(f"sound: {path} ({path.stat().st_size} bytes)")


def _tone(freq: float, dur: float, sr: int = 22050, vol: float = 0.6,
          decay: bool = True) -> list[float]:
    n = int(sr * dur)
    out = []
    for i in range(n):
        t = i / sr
        env = (1 - i / n) if decay else 1.0
        # 快速淡入避免爆音
        fade_in = min(1.0, i / (sr * 0.01))
        out.append(vol * env * fade_in * math.sin(2 * math.pi * freq * t))
    return out


def _silence(dur: float, sr: int = 22050) -> list[float]:
    return [0.0] * int(sr * dur)


def build_sounds():
    ASSETS.mkdir(parents=True, exist_ok=True)
    sr = 22050
    # chime: 清脆双音上行 C6→E6
    _write_wav(ASSETS / "chime.wav",
               _tone(1046.5, 0.16, sr) + _silence(0.02, sr) + _tone(1318.5, 0.30, sr))
    # ding: 单音叮咚（880Hz 长衰减）
    _write_wav(ASSETS / "ding.wav", _tone(880, 0.55, sr, vol=0.7))
    # alert: 紧急交替音（660/880 各两轮）
    alert = (_tone(660, 0.12, sr, decay=False) + _silence(0.03, sr)
             + _tone(880, 0.12, sr, decay=False) + _silence(0.03, sr)
             + _tone(660, 0.12, sr, decay=False) + _silence(0.03, sr)
             + _tone(880, 0.20, sr, decay=False))
    _write_wav(ASSETS / "alert.wav", alert)


# ---------------------------------------------------------------------------
# PNG 生成（复选框对勾，白色透明底）
def _seg_dist(px: float, py: float, ax: float, ay: float,
              bx: float, by: float) -> float:
    """点 (px,py) 到线段 AB 的最短距离。"""
    ab2 = (bx - ax) ** 2 + (by - ay) ** 2
    if ab2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ab2))
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))


def _write_png(path: Path, size: int, pixels: bytes):
    """pixels: size*size*4 RGBA。"""
    raw = b"".join(b"\x00" + pixels[y * size * 4:(y + 1) * size * 4]
                   for y in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def build_check_png(path: Path, size: int = 32):
    """白色对勾（透明底），用于 QSS 复选框选中态。"""
    s = float(size)
    # 对勾三段折线顶点（按 size 比例）
    pts = [(0.22 * s, 0.52 * s), (0.42 * s, 0.72 * s), (0.78 * s, 0.28 * s)]
    radius = s * 0.105          # 笔画半径
    px = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            d = min(_seg_dist(x + 0.5, y + 0.5, *pts[0], *pts[1]),
                    _seg_dist(x + 0.5, y + 0.5, *pts[1], *pts[2]))
            if d <= radius:
                # 边缘抗锯齿
                alpha = 255 if d <= radius - 1.2 else int(255 * max(0.0, (radius - d) / 1.2))
                i = (y * size + x) * 4
                px[i:i + 4] = bytes((255, 255, 255, alpha))
    _write_png(path, size, bytes(px))
    print(f"check png: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    build_icon(ROOT / "app.ico")
    # 复制一份到 assets，供打包后窗口/托盘图标使用
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "app.ico", ASSETS / "app.ico")
    build_check_png(ASSETS / "check.png")
    build_sounds()
    print("assets generated.")
