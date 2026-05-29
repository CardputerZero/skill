#!/usr/bin/env python3
"""Generate a simple function-aware APPLaunch PNG icon.

This intentionally uses only the Python standard library so it can run on a
fresh CardputerZero or CI host without Pillow/ImageMagick.
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import zlib
from pathlib import Path


Color = tuple[int, int, int, int]


PALETTES: dict[str, tuple[Color, Color, Color]] = {
    "calendar": ((33, 91, 163, 255), (248, 250, 252, 255), (239, 68, 68, 255)),
    "weather": ((14, 116, 144, 255), (236, 253, 245, 255), (250, 204, 21, 255)),
    "music": ((126, 34, 206, 255), (250, 245, 255, 255), (236, 72, 153, 255)),
    "calculator": ((22, 101, 52, 255), (240, 253, 244, 255), (34, 197, 94, 255)),
    "terminal": ((24, 24, 27, 255), (244, 244, 245, 255), (34, 197, 94, 255)),
    "game": ((124, 45, 18, 255), (255, 247, 237, 255), (249, 115, 22, 255)),
    "note": ((120, 53, 15, 255), (254, 252, 232, 255), (234, 179, 8, 255)),
    "network": ((30, 64, 175, 255), (239, 246, 255, 255), (59, 130, 246, 255)),
    "camera": ((55, 65, 81, 255), (249, 250, 251, 255), (14, 165, 233, 255)),
    "settings": ((51, 65, 85, 255), (248, 250, 252, 255), (148, 163, 184, 255)),
    "clock": ((127, 29, 29, 255), (254, 242, 242, 255), (248, 113, 113, 255)),
    "map": ((20, 83, 45, 255), (240, 253, 244, 255), (34, 197, 94, 255)),
    "file": ((67, 56, 202, 255), (238, 242, 255, 255), (129, 140, 248, 255)),
    "chat": ((8, 145, 178, 255), (236, 254, 255, 255), (6, 182, 212, 255)),
    "default": ((30, 41, 59, 255), (248, 250, 252, 255), (99, 102, 241, 255)),
}


KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("calendar", ("calendar", "schedule", "event", "date", "ics", "lunar", "holiday", "日历", "日程", "农历", "節日", "カレンダー")),
    ("weather", ("weather", "forecast", "temperature", "climate", "天气", "天気", "予報")),
    ("music", ("music", "audio", "sound", "player", "radio", "音乐", "音频", "音楽")),
    ("calculator", ("calculator", "calc", "math", "finance", "计算", "電卓", "計算")),
    ("terminal", ("terminal", "shell", "cli", "code", "ssh", "console", "终端", "代码")),
    ("game", ("game", "play", "arcade", "puzzle", "游戏", "ゲーム")),
    ("note", ("note", "memo", "text", "editor", "write", "markdown", "笔记", "メモ")),
    ("network", ("network", "web", "browser", "http", "wifi", "sync", "online", "网络", "同期")),
    ("camera", ("camera", "photo", "image", "scan", "qr", "相机", "写真")),
    ("settings", ("settings", "config", "admin", "manager", "control", "设置", "管理", "設定")),
    ("clock", ("clock", "timer", "alarm", "time", "pomodoro", "时钟", "闹钟", "時計")),
    ("map", ("map", "location", "gps", "nav", "route", "地图", "地図")),
    ("file", ("file", "folder", "storage", "backup", "archive", "文件", "ファイル")),
    ("chat", ("chat", "message", "mail", "social", "im", "聊天", "消息")),
]


def clamp(v: int) -> int:
    return max(0, min(255, v))


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(clamp(round(a[i] * (1.0 - t) + b[i] * t)) for i in range(4))  # type: ignore[return-value]


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "app"


def choose_kind(text: str) -> str:
    lowered = text.lower()
    for kind, words in KEYWORDS:
        if any(word.lower() in lowered for word in words):
            return kind
    return "default"


class Canvas:
    def __init__(self, size: int, background: Color) -> None:
        self.size = size
        self.pixels = [background] * (size * size)

    def set(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.size and 0 <= y < self.size:
            idx = y * self.size + x
            dst = self.pixels[idx]
            a = color[3] / 255.0
            self.pixels[idx] = (
                clamp(round(color[0] * a + dst[0] * (1 - a))),
                clamp(round(color[1] * a + dst[1] * (1 - a))),
                clamp(round(color[2] * a + dst[2] * (1 - a))),
                255,
            )

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        for y in range(max(0, y0), min(self.size, y1)):
            for x in range(max(0, x0), min(self.size, x1)):
                self.set(x, y, color)

    def round_rect(self, x0: int, y0: int, x1: int, y1: int, r: int, color: Color) -> None:
        for y in range(max(0, y0), min(self.size, y1)):
            for x in range(max(0, x0), min(self.size, x1)):
                cx = min(max(x, x0 + r), x1 - r - 1)
                cy = min(max(y, y0 + r), y1 - r - 1)
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r:
                    self.set(x, y, color)

    def circle(self, cx: int, cy: int, r: int, color: Color) -> None:
        rr = r * r
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= rr:
                    self.set(x, y, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, width: int, color: Color) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        radius = max(1, width // 2)
        for i in range(steps + 1):
            x = round(x0 + dx * i / steps)
            y = round(y0 + dy * i / steps)
            self.circle(x, y, radius, color)

    def polygon(self, points: list[tuple[int, int]], color: Color) -> None:
        min_y = max(0, min(p[1] for p in points))
        max_y = min(self.size - 1, max(p[1] for p in points))
        for y in range(min_y, max_y + 1):
            xs: list[float] = []
            for i, (x1, y1) in enumerate(points):
                x2, y2 = points[(i + 1) % len(points)]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for i in range(0, len(xs), 2):
                if i + 1 >= len(xs):
                    break
                self.rect(math.floor(xs[i]), y, math.ceil(xs[i + 1]), y + 1, color)


def draw_background(c: Canvas, base: Color, accent: Color) -> None:
    for y in range(c.size):
        for x in range(c.size):
            t = (x + y) / (2 * c.size)
            c.set(x, y, mix(base, accent, 0.20 + 0.35 * t))
    c.circle(c.size - 36, 42, 54, (255, 255, 255, 32))
    c.circle(32, c.size - 28, 62, (0, 0, 0, 24))


def draw_calendar(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(54, 56, 202, 204, 18, fg)
    c.round_rect(54, 56, 202, 88, 18, accent)
    c.rect(54, 74, 202, 92, accent)
    for x in (86, 170):
        c.round_rect(x, 42, x + 14, 72, 7, fg)
    for x in (76, 112, 148):
        c.line(x, 112, x, 178, 4, (30, 41, 59, 90))
    for y in (112, 144, 176):
        c.line(72, y, 184, y, 4, (30, 41, 59, 90))
    c.circle(112, 144, 12, accent)


def draw_weather(c: Canvas, fg: Color, accent: Color) -> None:
    c.circle(96, 86, 30, accent)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        c.line(96 + round(math.cos(rad) * 44), 86 + round(math.sin(rad) * 44), 96 + round(math.cos(rad) * 62), 86 + round(math.sin(rad) * 62), 8, accent)
    c.circle(112, 154, 36, fg)
    c.circle(150, 142, 44, fg)
    c.circle(184, 160, 28, fg)
    c.round_rect(84, 150, 206, 190, 20, fg)


def draw_music(c: Canvas, fg: Color, accent: Color) -> None:
    c.line(150, 62, 150, 166, 13, fg)
    c.line(150, 62, 194, 76, 13, fg)
    c.line(194, 76, 194, 146, 13, fg)
    c.circle(126, 170, 24, accent)
    c.circle(174, 150, 24, accent)


def draw_calculator(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(70, 42, 186, 214, 18, fg)
    c.round_rect(88, 62, 168, 94, 8, accent)
    for row in range(3):
        for col in range(3):
            c.round_rect(88 + col * 30, 116 + row * 28, 108 + col * 30, 136 + row * 28, 5, accent)


def draw_terminal(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(50, 60, 206, 196, 18, fg)
    c.line(78, 100, 104, 126, 8, accent)
    c.line(104, 126, 78, 152, 8, accent)
    c.line(124, 154, 172, 154, 8, accent)


def draw_game(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(44, 86, 212, 174, 36, fg)
    c.rect(78, 116, 130, 132, accent)
    c.rect(96, 98, 112, 150, accent)
    c.circle(166, 116, 12, accent)
    c.circle(190, 140, 12, accent)


def draw_note(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(70, 42, 184, 214, 14, fg)
    c.polygon([(150, 42), (184, 76), (150, 76)], accent)
    for y in (104, 128, 152, 176):
        c.line(92, y, 164, y, 5, accent)


def draw_network(c: Canvas, fg: Color, accent: Color) -> None:
    c.circle(128, 128, 70, fg)
    c.line(58, 128, 198, 128, 5, accent)
    c.line(128, 58, 128, 198, 5, accent)
    c.round_rect(80, 82, 176, 174, 48, (0, 0, 0, 0))
    for r in (34, 58):
        c.line(128 - r, 92, 128 + r, 92, 4, accent)
        c.line(128 - r, 164, 128 + r, 164, 4, accent)


def draw_camera(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(48, 78, 208, 184, 20, fg)
    c.round_rect(76, 58, 130, 88, 10, fg)
    c.circle(132, 132, 42, accent)
    c.circle(132, 132, 22, fg)


def draw_settings(c: Canvas, fg: Color, accent: Color) -> None:
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        c.line(128, 128, 128 + round(math.cos(rad) * 64), 128 + round(math.sin(rad) * 64), 18, fg)
    c.circle(128, 128, 54, fg)
    c.circle(128, 128, 26, accent)


def draw_clock(c: Canvas, fg: Color, accent: Color) -> None:
    c.circle(128, 128, 72, fg)
    c.circle(128, 128, 56, (255, 255, 255, 255))
    c.line(128, 128, 128, 86, 8, accent)
    c.line(128, 128, 162, 146, 8, accent)
    c.circle(128, 128, 8, accent)


def draw_map(c: Canvas, fg: Color, accent: Color) -> None:
    c.polygon([(70, 70), (112, 52), (112, 186), (70, 204)], fg)
    c.polygon([(112, 52), (154, 70), (154, 204), (112, 186)], accent)
    c.polygon([(154, 70), (196, 52), (196, 186), (154, 204)], fg)
    c.circle(142, 116, 24, (255, 255, 255, 255))
    c.circle(142, 116, 10, accent)


def draw_file(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(52, 82, 204, 194, 16, fg)
    c.round_rect(52, 62, 126, 102, 14, accent)
    c.rect(52, 86, 204, 112, fg)


def draw_chat(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(54, 62, 202, 166, 28, fg)
    c.polygon([(96, 162), (84, 206), (130, 166)], fg)
    for x in (96, 128, 160):
        c.circle(x, 114, 9, accent)


def draw_default(c: Canvas, fg: Color, accent: Color) -> None:
    c.round_rect(72, 54, 184, 202, 28, fg)
    c.circle(128, 112, 30, accent)
    c.round_rect(96, 152, 160, 176, 12, accent)


DRAWERS = {
    "calendar": draw_calendar,
    "weather": draw_weather,
    "music": draw_music,
    "calculator": draw_calculator,
    "terminal": draw_terminal,
    "game": draw_game,
    "note": draw_note,
    "network": draw_network,
    "camera": draw_camera,
    "settings": draw_settings,
    "clock": draw_clock,
    "map": draw_map,
    "file": draw_file,
    "chat": draw_chat,
    "default": draw_default,
}


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, canvas: Canvas) -> None:
    raw = bytearray()
    for y in range(canvas.size):
        raw.append(0)
        for x in range(canvas.size):
            raw.extend(canvas.pixels[y * canvas.size + x])
    ihdr = struct.pack(">IIBBBBB", canvas.size, canvas.size, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an app-specific APPLaunch PNG icon from app function text.")
    parser.add_argument("--app-name", required=True, help="Application display name.")
    parser.add_argument("--summary", default="", help="Short functional description, feature list, or app-builder summary.")
    parser.add_argument("--out", type=Path, help="Output PNG path. Defaults to ./share/images/<slug>.png")
    parser.add_argument("--size", type=int, default=256, help="Square icon size in pixels. Default: 256.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.size < 64 or args.size > 1024:
        raise SystemExit("--size must be between 64 and 1024")
    out = args.out or Path("share/images") / f"{slug(args.app_name)}.png"
    if out.exists() and not args.force:
        raise SystemExit(f"icon already exists: {out} (use --force to overwrite)")

    kind = choose_kind(f"{args.app_name} {args.summary}")
    base, fg, accent = PALETTES[kind]
    canvas = Canvas(args.size, base)
    draw_background(canvas, base, accent)
    scale = args.size / 256
    if abs(scale - 1.0) > 0.001:
        # Draw on a canonical 256 canvas, then nearest-neighbor scale. Icons are
        # intentionally geometric, so this keeps the drawing code simple.
        tmp = Canvas(256, base)
        draw_background(tmp, base, accent)
        DRAWERS[kind](tmp, fg, accent)
        for y in range(args.size):
            for x in range(args.size):
                canvas.pixels[y * args.size + x] = tmp.pixels[int(y / scale) * 256 + int(x / scale)]
    else:
        DRAWERS[kind](canvas, fg, accent)
    write_png(out, canvas)
    print(f"icon: {out}")
    print(f"kind: {kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
