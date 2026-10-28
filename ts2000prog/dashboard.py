"""Painel em tempo real do TS-2000 (visual moderno, não LCD).

Mostra tudo o que o rádio informa pela porta CAT: frequências, modo, VFO e
canal, RIT/XIT, split, tom, medidores de RX e TX, ganhos (AF, RF, SQL, MIC,
potência), banda passante do filtro DSP, AGC e os recursos ligados (PRE,
ATT, NB, NR, BC, PROC, VOX, AT, antena, trava). Escala com a janela.
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont

from common.ui import UI_FONT

from .protocol import SHIFTS, TONES
from .status import (SSB_HIGHCUT, SSB_LOWCUT, TX_METERS, RadioStatus,
                     extra_int)

MONO = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"
REF_W, REF_H = 1200, 600

THEMES = {
    "Escuro": {
        "bg": "#0e131b", "card": "#171f2b", "line": "#26324a",
        "text": "#e8edf5", "muted": "#8391a7", "dim": "#3a465c",
        "accent": "#ffb347", "ok": "#3fd17a", "tx": "#ff4d4d",
        "info": "#58a6ff", "warn": "#ffcc4d", "band": "#2f81f7",
    },
    "Claro": {
        "bg": "#eef1f6", "card": "#ffffff", "line": "#d5dbe5",
        "text": "#1b2433", "muted": "#5f6b7e", "dim": "#c9d1dc",
        "accent": "#d97706", "ok": "#15803d", "tx": "#dc2626",
        "info": "#1d4ed8", "warn": "#b45309", "band": "#2563eb",
    },
}


def fmt_freq(hz: int) -> tuple[str, str]:
    """14195050 -> ('14.195', '.05') em MHz com 10 Hz."""
    mhz, rest = divmod(hz, 1_000_000)
    return f"{mhz}.{rest // 1000:03d}", f".{(rest % 1000) // 10:02d}"


def s_units(v: int) -> str:
    """S-meter 0-30 (S9 = 15) em unidades S / dB acima de S9."""
    if v <= 15:
        return f"S{round(v * 9 / 15)}"
    return f"S9+{round((v - 15) * 60 / 15)}"


class Dashboard(tk.Canvas):
    def __init__(self, master, theme: str = "Escuro", **kw):
        super().__init__(master, highlightthickness=0, **kw)
        self.theme_name = theme
        self.status = RadioStatus()
        self.peak = 0.0
        self.bind("<Configure>", lambda e: self.redraw())

    @property
    def t(self) -> dict:
        return THEMES[self.theme_name]

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.redraw()

    def update_status(self, st: RadioStatus) -> None:
        # pico do S-meter com queda lenta
        self.peak = max(st.smeter, self.peak - 0.6)
        self.status = st
        self.redraw()

    # ------------------------------------------------------- primitivas
    def _xy(self, x, y):
        return self.ox + x * self.k, self.oy + y * self.k

    def _rect(self, x0, y0, x1, y1, fill, outline="", r=10, width=1):
        x0, y0 = self._xy(x0, y0)
        x1, y1 = self._xy(x1, y1)
        r = r * self.k
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r,
               x1, y1, x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r,
               x0, y0 + r, x0, y0]
        self.create_polygon(pts, smooth=True, fill=fill,
                            outline=outline or fill, width=width)

    def _text(self, x, y, text, size, color=None, anchor="nw",
              weight="normal", family=None):
        self.create_text(*self._xy(x, y), text=text, anchor=anchor,
                         fill=color or self.t["text"],
                         font=(family or UI_FONT, max(int(size * self.k), 6),
                               weight))

    def _measure(self, text, size, weight="normal", family=None) -> float:
        """Largura do texto em unidades de referência."""
        f = tkfont.Font(family=family or UI_FONT,
                        size=max(int(size * self.k), 6), weight=weight)
        return f.measure(text) / self.k

    def _card(self, x0, y0, x1, y1, title=None):
        self._rect(x0, y0, x1, y1, self.t["card"], self.t["line"])
        if title:
            self._text(x0 + 14, y0 + 10, title.upper(), 10,
                       self.t["muted"], weight="bold")

    def _chip(self, x, y, text, on, color=None, size=11):
        w = 18 + self._measure(text, size, "bold")
        fill = (color or self.t["info"]) if on else self.t["card"]
        fg = "#ffffff" if on else self.t["dim"]
        self._rect(x, y, x + w, y + size * 2.1, fill,
                   self.t["line"] if not on else fill, r=size)
        self._text(x + w / 2, y + size * 1.05, text, size, fg, "center",
                   "bold")
        return x + w + 8

    def _bar(self, x, y, w, h, frac, color, segments=0):
        self._rect(x, y, x + w, y + h, self.t["dim"], r=h / 2)
        frac = max(0.0, min(1.0, frac))
        if frac > 0:
            self._rect(x, y, x + max(w * frac, h), y + h, color, r=h / 2)
        for i in range(1, segments):
            xx = x + w * i / segments
            self.create_line(*self._xy(xx, y), *self._xy(xx, y + h),
                             fill=self.t["card"], width=max(self.k, 1))

    def _gauge(self, cx, cy, r, frac, label, value, color):
        """Mostrador em arco de 240 graus."""
        x0, y0 = self._xy(cx - r, cy - r)
        x1, y1 = self._xy(cx + r, cy + r)
        w = max(7 * self.k, 2)
        self.create_arc(x0, y0, x1, y1, start=-30, extent=240,
                        style="arc", outline=self.t["dim"], width=w)
        if frac is not None and frac > 0:
            ext = 240 * max(0.0, min(1.0, frac))
            self.create_arc(x0, y0, x1, y1, start=210 - ext, extent=ext,
                            style="arc", outline=color, width=w)
        self._text(cx, cy - 4, value, 15, anchor="center", weight="bold",
                   family=MONO)
        self._text(cx, cy + r * 0.62, label, 10, self.t["muted"], "center",
                   "bold")

    # ---------------------------------------------------------- desenho
    def redraw(self) -> None:
        self.delete("all")
        W, H = self.winfo_width(), self.winfo_height()
        if W < 60 or H < 40:
            return
        self.k = min(W / REF_W, H / REF_H)
        self.ox = (W - REF_W * self.k) / 2
        self.oy = (H - REF_H * self.k) / 2
        self.configure(bg=self.t["bg"])
        st = self.status
        if not st.connected:
            self._text(REF_W / 2, REF_H / 2 - 20, "Sem conexão com o rádio",
                       26, self.t["muted"], "center", "bold")
            self._text(REF_W / 2, REF_H / 2 + 22,
                       "Conecte o TS-2000 no programador para ver o painel",
                       13, self.t["muted"], "center")
            return
        self._top_bar(st)
        self._main_freq(st)
        self._meters(st)
        self._gauges(st)
        self._filter(st)
        self._features(st)

    def _top_bar(self, st: RadioStatus) -> None:
        t = self.t
        x = 20
        x = self._chip(x, 16, "TX" if st.tx else "RX", True,
                       t["tx"] if st.tx else t["ok"], 13)
        vfo = {0: "VFO A", 1: "VFO B"}.get(st.vfo, f"MEM {st.channel:03d}")
        x = self._chip(x, 16, vfo, True, t["info"], 13)
        busy = st.extra.get("busy", "")[:1] == "1"
        x = self._chip(x, 16, "OCUPADO", busy, t["warn"], 13)
        x = self._chip(x, 16, "SPLIT", st.split, t["accent"], 13)
        x = self._chip(x, 16, "SCAN", st.scan, t["accent"], 13)
        x = self._chip(x, 16, "LOCK", st.extra.get("lock", "0")[:1] not in
                       ("0", ""), t["warn"], 13)
        ant = st.extra.get("ant", "")
        if ant:
            x = self._chip(x, 16, f"ANT {ant}", True, t["info"], 13)

    def _main_freq(self, st: RadioStatus) -> None:
        t = self.t
        self._card(20, 64, 700, 300, "Principal")
        big, small = fmt_freq(st.freq)
        self._text(40, 92, big, 76, t["tx"] if st.tx else t["text"],
                   weight="bold", family=MONO)
        self._text(44 + self._measure(big, 76, "bold", MONO), 128,
                   small + " MHz", 30,
                   t["muted"], family=MONO)
        # linha de detalhes
        y = 210
        x = self._chip(40, y, st.mode_name or "—", True, t["accent"], 16)
        if st.rit or st.xit:
            lab = ("RIT" if st.rit else "") + ("/XIT" if st.xit and st.rit
                                               else "XIT" if st.xit else "")
            x = self._chip(x, y, f"{lab} {st.rit_offset / 1000:+.2f} kHz",
                           True, t["info"], 14)
        if st.tone_mode:
            idx = extra_int(st, "ctcss" if st.tone_mode == 2 else "tone")
            name = {1: "TONE", 2: "CTCSS", 3: "DCS"}[st.tone_mode]
            hz = f" {TONES[idx - 1]:.1f} Hz" if st.tone_mode in (1, 2) and \
                idx and 1 <= idx <= len(TONES) else ""
            x = self._chip(x, y, name + hz, True, t["info"], 14)
        if st.shift:
            x = self._chip(x, y, f"SHIFT {SHIFTS[st.shift]}", True,
                           t["info"], 14)
        # VFO B
        self._text(40, 262, "VFO B", 12, t["muted"], weight="bold")
        if st.freq_b:
            b1, b2 = fmt_freq(st.freq_b)
            self._text(110, 256, b1 + b2 + " MHz", 20, t["text"],
                       family=MONO)

    def _meters(self, st: RadioStatus) -> None:
        t = self.t
        self._card(716, 64, 1180, 300, "Medidores")
        x, w = 740, 416
        if st.tx:
            frac = st.smeter / 30
            self._text(x, 96, "PO  potência", 12, t["muted"], weight="bold")
            self._bar(x, 118, w, 18, frac, t["tx"], 30)
            pw = st.power or 100
            self._text(x + w, 96, f"≈ {round(frac * pw * 1.0)} W", 12,
                       t["text"], "ne", "bold", MONO)
            tm = st.extra.get("txmeter", "")
            kind = TX_METERS.get(tm[:1], "ALC") if tm else "ALC"
            val = extra_int(st, "txmeter", 0) % 10000 if tm else 0
            self._text(x, 152, kind, 12, t["muted"], weight="bold")
            self._bar(x, 174, w, 14, val / 30, t["warn"], 30)
            self._text(x + w, 152, str(val), 12, t["text"], "ne", "bold",
                       MONO)
        else:
            self._text(x, 96, "S  sinal principal", 12, t["muted"],
                       weight="bold")
            self._bar(x, 118, w, 18, st.smeter / 30,
                      t["ok"] if st.smeter <= 15 else t["accent"], 30)
            pk = x + w * min(self.peak / 30, 1)
            self.create_line(*self._xy(pk, 114), *self._xy(pk, 140),
                             fill=t["text"], width=max(2 * self.k, 1))
            self._text(x + w, 96, s_units(st.smeter), 13, t["text"], "ne",
                       "bold", MONO)
            for lab, pos in (("1", 1.7), ("3", 5), ("5", 8.3), ("7", 11.7),
                             ("9", 15), ("+20", 20), ("+40", 25),
                             ("+60", 30)):
                self._text(x + w * pos / 30, 142, lab, 9, t["muted"], "n")
            sub = extra_int(st, "smeter_sub")
            if sub is not None:
                self._text(x, 170, "S  sub-receptor", 12, t["muted"],
                           weight="bold")
                self._bar(x, 192, w, 10, sub / 15, t["info"], 15)
        self._text(x, 222, "Potência ajustada", 11, t["muted"])
        self._text(x + w, 222, f"{st.power} W" if st.power is not None
                   else "—", 11, t["text"], "ne", "bold", MONO)
        self._text(x, 248, "AGC", 11, t["muted"])
        agc = extra_int(st, "agc")
        self._text(x + w, 248, "OFF" if agc == 0 else (str(agc) if agc
                                                        else "—"),
                   11, t["text"], "ne", "bold", MONO)
        ks = extra_int(st, "keyer")
        if ks and st.mode in (3, 7):
            self._text(x, 272, "Keyer", 11, t["muted"])
            self._text(x + w, 272, f"{ks} wpm", 11, t["text"], "ne", "bold",
                       MONO)

    def _gauges(self, st: RadioStatus) -> None:
        t = self.t
        self._card(20, 316, 700, 584, "Ganhos")
        items = [
            ("AF", extra_int(st, "af"), 255, t["ok"]),
            ("RF", extra_int(st, "rf"), 255, t["info"]),
            ("SQL", extra_int(st, "sql"), 255, t["warn"]),
            ("MIC", extra_int(st, "mic"), 100, t["accent"]),
            ("PWR", st.power, 100, t["tx"]),
        ]
        for i, (lab, v, mx, color) in enumerate(items):
            cx = 90 + i * 130
            frac = None if v is None else v / mx
            txt = "—" if v is None else f"{round(v * 100 / mx)}%"
            if lab == "PWR" and v is not None:
                txt = f"{v}W"
            self._gauge(cx, 430, 50, frac, lab, txt, color)
        nb, nr = extra_int(st, "nblevel"), extra_int(st, "nrlevel")
        y = 520
        x = 40
        x = self._chip(x, y, "PRE", st.preamp, t["info"])
        x = self._chip(x, y, "ATT", st.att, t["warn"])
        x = self._chip(x, y, f"NB {nb}" if st.nb and nb else "NB", st.nb,
                       t["ok"])
        x = self._chip(x, y, (f"NR{st.nr} {nr}" if st.nr and nr else
                              f"NR{st.nr or ''}"), st.nr != 0, t["ok"])
        bc = extra_int(st, "bc", 0)
        x = self._chip(x, y, f"BC{bc}" if bc else "BC", bc != 0, t["ok"])

    def _filter(self, st: RadioStatus) -> None:
        t = self.t
        self._card(716, 316, 1180, 470, "Filtro DSP")
        x0, x1, y0, y1 = 740, 1156, 352, 424
        self.create_line(*self._xy(x0, y1), *self._xy(x1, y1),
                         fill=t["muted"], width=max(self.k, 1))
        lo_i, hi_i = extra_int(st, "lowcut"), extra_int(st, "highcut")
        width = extra_int(st, "width")
        ssb = st.mode in (1, 2)
        span = 5000
        if ssb and lo_i is not None and hi_i is not None and \
                lo_i < len(SSB_LOWCUT) and hi_i < len(SSB_HIGHCUT):
            lo, hi = SSB_LOWCUT[lo_i], SSB_HIGHCUT[hi_i]
            label = f"{lo} – {hi} Hz  (largura {hi - lo} Hz)"
        elif width:
            lo, hi = max(0, 1500 - width // 2), min(span, 1500 + width // 2)
            label = f"largura {width} Hz"
        else:
            lo = hi = None
            label = "—"
        if lo is not None:
            xa = x0 + (x1 - x0) * lo / span
            xb = x0 + (x1 - x0) * hi / span
            sl = 18
            pts = [xa, y1, xa + sl, y0, xb - sl, y0, xb, y1]
            self.create_polygon([c for i in range(0, 8, 2)
                                 for c in self._xy(pts[i], pts[i + 1])],
                                fill=t["band"], outline=t["band"],
                                stipple="" if sys.platform == "win32"
                                else "")
        shift = extra_int(st, "ifshift")
        if shift:
            xs = x0 + (x1 - x0) * (1500 + shift) / span
            self.create_line(*self._xy(xs, y0 - 6), *self._xy(xs, y1),
                             fill=t["accent"], width=max(2 * self.k, 1),
                             dash=(4, 3))
        for f in (0, 1000, 2000, 3000, 4000, 5000):
            self._text(x0 + (x1 - x0) * f / span, y1 + 4, f"{f // 1000}k",
                       9, t["muted"], "n")
        self._text(x0, 454, label, 11, t["text"], "w", "bold")
        if shift:
            self._text(x1, 454, f"IF shift {shift:+d} Hz", 11,
                       t["accent"], "e")

    def _features(self, st: RadioStatus) -> None:
        t = self.t
        self._card(716, 486, 1180, 584, "Transmissão")
        tuner = st.extra.get("tuner", "")
        at_on = len(tuner) >= 2 and tuner[1] == "1"
        tuning = len(tuner) >= 3 and tuner[2] == "1"
        x, y = 740, 528
        x = self._chip(x, y, "PROC", st.extra.get("proc", "0")[:1] == "1",
                       t["accent"])
        x = self._chip(x, y, "VOX", st.extra.get("vox", "0")[:1] == "1",
                       t["accent"])
        x = self._chip(x, y, "AT SINT." if tuning else "AT", at_on or tuning,
                       t["warn"] if tuning else t["ok"])
        mic = extra_int(st, "mic")
        if mic is not None:
            self._text(x + 6, y + 11, f"MIC {mic}", 11, t["muted"], "w")
