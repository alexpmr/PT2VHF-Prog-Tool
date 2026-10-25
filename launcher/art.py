"""Ilustrações da tela inicial (logotipos e rádios), desenhadas em Canvas.

Se existir um arquivo com o mesmo nome em `assets/` (PNG ou GIF), ele é
usado no lugar do desenho: kenwood.png, icom.png, ts2000.png,
id51plus2.png e id880h.png. Assim é possível colocar fotos reais dos rádios.
"""

from __future__ import annotations

import os
import tkinter as tk

ASSETS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "assets")


def load_asset(name: str, max_w: int, max_h: int) -> tk.PhotoImage | None:
    for ext in (".png", ".gif"):
        path = os.path.join(ASSETS, name + ext)
        if os.path.isfile(path):
            try:
                img = tk.PhotoImage(file=path)
            except tk.TclError:
                return None
            factor = max(1, -(-img.width() // max_w), -(-img.height() // max_h))
            return img.subsample(factor) if factor > 1 else img
    return None


def _rrect(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


# ------------------------------------------------------------ logotipos

def draw_kenwood(c: tk.Canvas, w: int, h: int) -> None:
    _rrect(c, 6, 6, w - 6, h - 6, 14, fill="#111111", outline="")
    c.create_text(w / 2, h / 2 - 4, text="KENWOOD", fill="#ffffff",
                  font=("Helvetica", int(min(h * 0.26, w * 0.085)), "bold"))
    c.create_rectangle(w * 0.22, h * 0.72, w * 0.78, h * 0.72 + 3,
                       fill="#d4282e", outline="")


def draw_icom(c: tk.Canvas, w: int, h: int) -> None:
    _rrect(c, 6, 6, w - 6, h - 6, 14, fill="#ffffff", outline="#1d4f91",
           width=3)
    c.create_text(w / 2, h / 2, text="ICOM", fill="#1d4f91",
                  font=("Helvetica", int(h * 0.34), "bold italic"))


# --------------------------------------------------------------- rádios

def draw_ts2000(c: tk.Canvas, w: int, h: int) -> None:
    """Transceptor de mesa: painel largo, LCD âmbar e dial grande."""
    x0, y0, x1, y1 = w * 0.04, h * 0.18, w * 0.96, h * 0.86
    c.create_rectangle(x0 + 4, y1, x0 + 18, y1 + h * 0.06, fill="#222",
                       outline="")
    c.create_rectangle(x1 - 18, y1, x1 - 4, y1 + h * 0.06, fill="#222",
                       outline="")
    _rrect(c, x0, y0, x1, y1, 8, fill="#3a3d42", outline="#1c1d20", width=2)
    pw, ph = x1 - x0, y1 - y0
    # LCD
    c.create_rectangle(x0 + pw * 0.24, y0 + ph * 0.10, x0 + pw * 0.66,
                       y0 + ph * 0.42, fill="#f0a030", outline="#1c1d20")
    c.create_text(x0 + pw * 0.45, y0 + ph * 0.26, text="14.195.00",
                  fill="#2a1500", font=("Courier", max(int(ph * 0.14), 7),
                                        "bold"))
    # dial principal
    cx, cy, r = x0 + pw * 0.48, y0 + ph * 0.70, ph * 0.22
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#16171a",
                  outline="#5a5d63", width=2)
    c.create_oval(cx + r * 0.3, cy - r * 0.6, cx + r * 0.55, cy - r * 0.35,
                  fill="#4a4d52", outline="")
    # botões e knobs
    for i in range(4):
        bx = x0 + pw * (0.05 + i * 0.045)
        c.create_rectangle(bx, y0 + ph * 0.15, bx + pw * 0.03,
                           y0 + ph * 0.24, fill="#9aa0a8", outline="")
    for kx in (0.10, 0.18):
        k = ph * 0.12
        c.create_oval(x0 + pw * kx - k, y0 + ph * 0.62 - k,
                      x0 + pw * kx + k, y0 + ph * 0.62 + k, fill="#222",
                      outline="#666")
    for row in range(3):
        for col in range(4):
            bx = x0 + pw * (0.70 + col * 0.06)
            by = y0 + ph * (0.14 + row * 0.13)
            c.create_rectangle(bx, by, bx + pw * 0.045, by + ph * 0.08,
                               fill="#c8ccd2", outline="")
    for kx in (0.74, 0.86):
        k = ph * 0.11
        c.create_oval(x0 + pw * kx - k, y0 + ph * 0.72 - k,
                      x0 + pw * kx + k, y0 + ph * 0.72 + k, fill="#222",
                      outline="#666")
    c.create_text(x0 + pw * 0.12, y0 + ph * 0.90, text="TS-2000",
                  fill="#d9dce1", font=("Helvetica", max(int(ph * 0.09), 6),
                                        "bold"))


def draw_id51(c: tk.Canvas, w: int, h: int) -> None:
    """Portátil: corpo alto, antena, display e teclado."""
    bw, bh = w * 0.34, h * 0.70
    x0, y0 = (w - bw) / 2, h * 0.24
    c.create_rectangle(x0 + bw * 0.15, y0 - h * 0.18, x0 + bw * 0.28, y0,
                       fill="#1b1b1b", outline="")
    c.create_rectangle(x0 + bw * 0.62, y0 - h * 0.05, x0 + bw * 0.80, y0,
                       fill="#555", outline="")
    _rrect(c, x0, y0, x0 + bw, y0 + bh, 10, fill="#2b2e33",
           outline="#111", width=2)
    c.create_rectangle(x0 + bw * 0.12, y0 + bh * 0.08, x0 + bw * 0.88,
                       y0 + bh * 0.36, fill="#cfe3f2", outline="#111")
    c.create_text(x0 + bw / 2, y0 + bh * 0.22, text="439.975",
                  fill="#102030", font=("Courier", max(int(bh * 0.07), 6),
                                        "bold"))
    for row in range(4):
        for col in range(3):
            kx = x0 + bw * (0.14 + col * 0.26)
            ky = y0 + bh * (0.44 + row * 0.12)
            c.create_rectangle(kx, ky, kx + bw * 0.2, ky + bh * 0.08,
                               fill="#8d939b", outline="")
    c.create_text(x0 + bw / 2, y0 + bh * 0.95, text="ICOM", fill="#9ec1ea",
                  font=("Helvetica", max(int(bh * 0.06), 6), "bold"))


def draw_id880(c: tk.Canvas, w: int, h: int) -> None:
    """Móvel: corpo baixo e largo, display central e dois knobs."""
    x0, y0, x1, y1 = w * 0.06, h * 0.30, w * 0.94, h * 0.78
    _rrect(c, x0, y0, x1, y1, 8, fill="#26282c", outline="#0e0f10", width=2)
    pw, ph = x1 - x0, y1 - y0
    c.create_rectangle(x0 + pw * 0.26, y0 + ph * 0.16, x0 + pw * 0.74,
                       y0 + ph * 0.62, fill="#ff9d2e", outline="#111")
    c.create_text(x0 + pw * 0.5, y0 + ph * 0.39, text="145.500",
                  fill="#2a1500", font=("Courier", max(int(ph * 0.2), 6),
                                        "bold"))
    for kx in (0.12, 0.88):
        k = ph * 0.26
        c.create_oval(x0 + pw * kx - k, y0 + ph * 0.5 - k,
                      x0 + pw * kx + k, y0 + ph * 0.5 + k, fill="#111",
                      outline="#777", width=2)
    for i in range(6):
        bx = x0 + pw * (0.28 + i * 0.075)
        c.create_rectangle(bx, y0 + ph * 0.72, bx + pw * 0.055,
                           y0 + ph * 0.88, fill="#9aa0a8", outline="")


DRAWINGS = {
    "kenwood": draw_kenwood, "icom": draw_icom, "ts2000": draw_ts2000,
    "id51plus2": draw_id51, "id880h": draw_id880,
}


class Picture(tk.Canvas):
    """Canvas que mostra a imagem de assets/ ou o desenho padrão."""

    def __init__(self, master, name: str, width: int, height: int, **kw):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, **kw)
        self.photo = load_asset(name, width, height)
        if self.photo is not None:
            self.create_image(width / 2, height / 2, image=self.photo)
        else:
            DRAWINGS[name](self, width, height)
