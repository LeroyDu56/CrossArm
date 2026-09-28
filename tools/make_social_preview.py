# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Draw CrossArm's two banner images with Tk, standard library only.

    python tools/make_social_preview.py        (Windows: images are captured with PrintWindow)

    docs/images/social_preview.png   1280 x 640: the card shown when a link to the repository is
                                     shared (GitHub: Settings > General > Social preview), and the
                                     page image of the site
    packaging/splash.png             560 x 280: shown by CrossArm.exe the moment it is launched,
                                     while it unpacks (2 to 3 s with nothing on screen otherwise)
"""

import base64
import ctypes
import struct
import sys
import time
import tkinter as tk
import zlib
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_icon

FONT = "Segoe UI"
NAVY, TEAL, LIGHT, MUTED = "#1F2A44", "#2EC4B6", "#D5DCEA", "#9AA8C3"


def draw_social(canvas: tk.Canvas, icon: tk.PhotoImage, width: int, height: int) -> None:
    canvas.create_rectangle(0, 0, width, height, fill=NAVY, outline="")
    canvas.create_rectangle(0, height - 14, width, height, fill=TEAL, outline="")
    canvas.create_image(110, 125, image=icon, anchor="nw")
    canvas.create_text(360, 130, text="CrossArm", anchor="nw", fill="white", font=(FONT, -104, "bold"))
    canvas.create_text(364, 270, text="ABB RAPID  →  FANUC TP converter", anchor="nw", fill=LIGHT, font=(FONT, -46))
    canvas.create_text(366, 345, anchor="nw", fill=MUTED, font=(FONT, -28), text=(
        "Motions, frames, I/O, registers and logic, from a RobotWare backup\n"
        "to .LS programs, with a report of everything left to review."
    ))  # fmt: skip
    canvas.create_text(110, 530, text="github.com/LeroyDu56/CrossArm", anchor="nw", fill=TEAL,
                       font=(FONT, -30, "bold"))  # fmt: skip
    canvas.create_text(width - 110, 536, text="offline · Windows exe · Python", anchor="ne", fill=MUTED,
                       font=(FONT, -26))  # fmt: skip


def draw_splash(canvas: tk.Canvas, icon: tk.PhotoImage, width: int, height: int) -> None:
    canvas.create_rectangle(0, 0, width, height, fill=NAVY, outline="")
    canvas.create_rectangle(0, height - 8, width, height, fill=TEAL, outline="")
    canvas.create_image(48, 70, image=icon, anchor="nw")
    canvas.create_text(190, 72, text="CrossArm", anchor="nw", fill="white", font=(FONT, -58, "bold"))
    canvas.create_text(192, 150, text="ABB RAPID  →  FANUC TP", anchor="nw", fill=LIGHT, font=(FONT, -24))
    canvas.create_text(48, 226, text="Starting…", anchor="nw", fill=MUTED, font=(FONT, -18))


def capture(window: tk.Tk, width: int, height: int) -> bytes:
    """The window rendered by itself, as PNG scanlines (never a copy of the screen)."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for _ in range(10):  # a new window needs a few rounds to be painted: captured too early, it is black
        window.update()
        time.sleep(0.03)
    hwnd = user32.GetParent(window.winfo_id())
    screen = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(screen)
    bmp = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(mem, bmp)
    if not user32.PrintWindow(hwnd, mem, 2):
        raise RuntimeError("PrintWindow failed")

    class Header(ctypes.Structure):
        _fields_ = [(n, t) for n, t in (
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
        )]  # fmt: skip

    header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem, bmp, 0, height, buf, ctypes.byref(header), 0)
    for handle in (bmp, mem):
        gdi32.DeleteObject(handle)
    user32.ReleaseDC(0, screen)
    raw = bytearray()
    for y in range(height):
        row = buf.raw[y * width * 4 : (y + 1) * width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        raw += b"\x00" + rgb
    return bytes(raw)


def png(raw_rows: bytes, width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw_rows, 9)) + chunk(b"IEND", b"")


def render(draw, width: int, height: int, icon_size: int, target: Path) -> None:
    window = tk.Tk()
    window.overrideredirect(True)  # no title bar in the capture
    window.geometry(f"{width}x{height}+0+0")
    icon = tk.PhotoImage(data=base64.b64encode(make_icon.png(icon_size, make_icon.render(icon_size))))
    canvas = tk.Canvas(window, width=width, height=height, highlightthickness=0, borderwidth=0)
    canvas.pack()
    draw(canvas, icon, width, height)
    target.write_bytes(png(capture(window, width, height), width, height))
    window.destroy()
    print(f"wrote {target.relative_to(ROOT)}")


def main() -> None:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # pixels, not scaled points
    render(draw_social, 1280, 640, 200, ROOT / "docs" / "images" / "social_preview.png")
    render(draw_splash, 560, 280, 120, ROOT / "packaging" / "splash.png")


if __name__ == "__main__":
    main()
