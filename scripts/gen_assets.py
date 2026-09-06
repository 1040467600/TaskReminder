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
_SS = 4          # 超采样倍率（抗锯齿）


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _icon_pixel(x: float, y: float, s: float):
    """计算逻辑坐标 (x,y) 处的 RGBA；不在圆角方块内返回 None。"""
    cx = cy = s / 2
    half = s * 0.48
    rr = s * 0.215
    dx = max(abs(x - cx) - (half - rr), 0)
    dy = max(abs(y - cy) - (half - rr), 0)
    if dx * dx + dy * dy > rr * rr:
        return None

    # 背景：垂直渐变 #4F8DF9(上) → #1D4ED8(下)
    t = max(0.0, min(1.0, (y - (cy - half)) / (2 * half)))
    r, g, b = _lerp(0x4F, 0x1D, t), _lerp(0x8D, 0x4E, t), _lerp(0xF9, 0xD8, t)

    # 顶部柔光高光（上 40% 区域，白色淡入）
    if y < cy - half * 0.2:
        glow = (cy - half * 0.2 - y) / (s * 0.68) * 0.30
        r = _lerp(r, 255, glow); g = _lerp(g, 255, glow); b = _lerp(b, 255, glow)

    # --- 铃铛 ---
    ytop = cy - s * 0.30        # 铃顶
    yrim = cy + s * 0.14        # 铃口
    rim_half = s * 0.27         # 铃口半宽
    in_body = False
    if ytop <= y <= yrim:
        tt = (y - ytop) / (yrim - ytop)
        if abs(x - cx) <= rim_half * (0.16 + 0.84 * (tt ** 0.68)):
            in_body = True
    # 铃口横条
    if yrim < y <= yrim + s * 0.045 and abs(x - cx) <= rim_half:
        in_body = True
    # 铃锤
    cl_r = s * 0.062
    if math.hypot(x - cx, y - (yrim + s * 0.045 + cl_r * 0.8)) <= cl_r:
        in_body = True
    if in_body:
        # 铃身白色，底部略带冷灰更有立体感
        ts = max(0.0, min(1.0, (y - ytop) / (yrim - ytop + 0.001)))
        r = _lerp(255, 0xDC, ts * 0.5); g = _lerp(255, 0xE7, ts * 0.5); b = _lerp(255, 0xFB, ts * 0.5)

    # --- 红色消息角标（右上，白色描边） ---
    bx, by, br = cx + s * 0.275, cy - s * 0.275, s * 0.125
    d = math.hypot(x - bx, y - by)
    if d <= br + s * 0.028:
        if d <= br:
            r, g, b = 0xEF, 0x44, 0x44          # #EF4444
        else:
            r = g = b = 255                      # 白色描边
    return r, g, b, 255


def _draw_icon(size: int) -> bytes:
    """绘制图标帧：蓝色渐变圆角方块 + 白色铃铛 + 红色角标（超采样抗锯齿）。"""
    big = size * _SS
    canvas = bytearray(big * big * 4)
    for y in range(big):
        for x in range(big):
            p = _icon_pixel((x + 0.5) / _SS, (y + 0.5) / _SS, size)
            if p is not None:
                i = (y * big + x) * 4
                canvas[i:i + 4] = bytes(int(c) for c in p)

    # 盒式降采样（box filter）
    px = bytearray(size * size * 4)
    n = _SS * _SS
    for y in range(size):
        for x in range(size):
            rs = gs = bs = as_ = 0
            for sy in range(_SS):
                base = ((y * _SS + sy) * big + x * _SS) * 4
                for sx in range(_SS):
                    i = base + sx * 4
                    rs += canvas[i]; gs += canvas[i + 1]
                    bs += canvas[i + 2]; as_ += canvas[i + 3]
            i = (y * size + x) * 4
            # ICO BMP 帧像素序为 BGRA
            px[i:i + 4] = bytes((bs // n, gs // n, rs // n, as_ // n))
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
