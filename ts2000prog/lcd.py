"""Display secundário do TS-2000, simulando um LCD grande.

Desenhado em um Canvas com dígitos de 7 segmentos (segmentos apagados ficam
"fantasma", como num LCD real). Escala com o tamanho da janela; F11 alterna
tela cheia e o botão direito abre o menu de temas.
"""

from __future__ import annotations

import tkinter as tk

from common.ui import UI_FONT

from .status import RadioStatus

THEMES = {
    "Âmbar (TS-2000)": {"bg": "#f0a030", "on": "#1a0f00", "off": "#e39528",
                         "tx": "#b00000", "frame": "#2b2b2b"},
    "Verde": {"bg": "#9fc46a", "on": "#0f2005", "off": "#93b862",
              "tx": "#8a0000", "frame": "#2b2b2b"},
    "Azul noturno": {"bg": "#06121f", "on": "#5fd7ff", "off": "#0d2236",
                     "tx": "#ff4040", "frame": "#000000"},
    "Vermelho noturno": {"bg": "#120404", "on": "#ff5a3c", "off": "#2a0b07",
                         "tx": "#ffd23c", "frame": "#000000"},
}

#  a
# f b
#  g
# e c
#  d
SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
    "-": "g", " ": "", "E": "afged", "r": "eg", "o": "cdeg", "n": "ceg",
    "P": "abefg", "L": "fed", "A": "abcefg", "b": "cdefg", "C": "adef",
    "d": "bcdeg", "F": "aefg", "H": "bcefg", "U": "bcdef", "S": "afgcd",
    "t": "defg",
}

REF_W, REF_H = 1000, 330


class LcdCanvas(tk.Canvas):
    def __init__(self, master, theme: str = "Âmbar (TS-2000)", **kw):
        super().__init__(master, highlightthickness=0, **kw)
        self.theme_name = theme
        self.status = RadioStatus()
        self.bind("<Configure>", lambda e: self.redraw())

    @property
    def t(self) -> dict:
        return THEMES[self.theme_name]

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.redraw()

    def update_status(self, st: RadioStatus) -> None:
        self.status = st
        self.redraw()

    # -------------------------------------------------------- primitivas
    def _xy(self, x: float, y: float) -> tuple[float, float]:
        return self.ox + x * self.k, self.oy + y * self.k

    def _digit(self, x: float, y: float, w: float, h: float, ch: str,
               lit: bool = True) -> None:
        """Dígito de 7 segmentos inclinado com canto superior esquerdo x,y."""
        th = max(w * 0.22, 2.5)
        slant = w * 0.12
        segs = SEGMENTS.get(ch, "")
        half = h / 2

        def sk(px, py):        # aplica inclinação
            return px + slant * (1 - (py - y) / h), py

        def hseg(py):
            x0, x1 = x + th * 0.6, x + w - th * 0.6
            return [sk(x0, py), sk(x0 + th / 2, py - th / 2),
                    sk(x1 - th / 2, py - th / 2), sk(x1, py),
                    sk(x1 - th / 2, py + th / 2),
                    sk(x0 + th / 2, py + th / 2)]

        def vseg(px, y0, y1):
            y0, y1 = y0 + th * 0.6, y1 - th * 0.6
            return [sk(px, y0), sk(px + th / 2, y0 + th / 2),
                    sk(px + th / 2, y1 - th / 2), sk(px, y1),
                    sk(px - th / 2, y1 - th / 2),
                    sk(px - th / 2, y0 + th / 2)]

        shapes = {
            "a": hseg(y + th / 2), "g": hseg(y + half),
            "d": hseg(y + h - th / 2),
            "f": vseg(x + th / 2, y, y + half),
            "b": vseg(x + w - th / 2, y, y + half),
            "e": vseg(x + th / 2, y + half, y + h),
            "c": vseg(x + w - th / 2, y + half, y + h),
        }
        for name, pts in shapes.items():
            on = lit and name in segs
            flat = [c for p in pts for c in self._xy(*p)]
            self.create_polygon(flat, fill=self.t["on"] if on else
                                self.t["off"], outline="")

    def _text(self, x, y, text, size, lit=True, anchor="nw", bold=True,
              color=None):
        fill = color or (self.t["on"] if lit else self.t["off"])
        self.create_text(*self._xy(x, y), text=text, anchor=anchor,
                         fill=fill, font=(UI_FONT, max(int(size * self.k),
                                                           6),
                                          "bold" if bold else "normal"))

    def _dot(self, x, y, r, lit=True):
        x0, y0 = self._xy(x - r, y - r)
        x1, y1 = self._xy(x + r, y + r)
        self.create_oval(x0, y0, x1, y1, outline="",
                         fill=self.t["on"] if lit else self.t["off"])

    def _number(self, x, y, w, h, gap, text, lit=True):
        """Escreve uma sequência de dígitos; '.' vira ponto decimal."""
        cx = x
        for ch in text:
            if ch == ".":
                self._dot(cx - gap * 0.5, y + h - w * 0.08, max(w * 0.1, 2.5), lit)
                continue
            self._digit(cx, y, w, h, ch, lit)
            cx += w + gap
        return cx

    # ----------------------------------------------------------- desenho
    def redraw(self) -> None:
        self.delete("all")
        W, H = self.winfo_width(), self.winfo_height()
        if W < 50 or H < 30:
            return
        self.k = min(W / REF_W, H / REF_H)
        self.ox = (W - REF_W * self.k) / 2
        self.oy = (H - REF_H * self.k) / 2
        self.configure(bg=self.t["frame"])
        x0, y0 = self._xy(4, 4)
        x1, y1 = self._xy(REF_W - 4, REF_H - 4)
        self.create_rectangle(x0, y0, x1, y1, fill=self.t["bg"],
                              outline=self.t["off"], width=2)
        st = self.status
        live = st.connected

        # ---- linha de indicadores
        ind = [
            ("TX" if st.tx else "RX", True,
             self.t["tx"] if st.tx and live else None),
            ({0: "VFO A", 1: "VFO B", 2: "M.CH"}.get(st.vfo, "VFO"), True,
             None),
            ("SPLIT", st.split, None), ("RIT", st.rit, None),
            ("XIT", st.xit, None),
            ({1: "TONE", 2: "CTCSS", 3: "DCS"}.get(st.tone_mode, "TONE"),
             st.tone_mode != 0, None),
            ({1: "+", 2: "–", 3: "="}.get(st.shift, "+"), st.shift != 0, None),
            ("PRE", st.preamp, None), ("ATT", st.att, None),
            ("NB", st.nb, None),
            (f"NR{st.nr or 1}", st.nr != 0, None), ("SCAN", st.scan, None),
        ]
        x = 30
        for text, on, color in ind:
            self._text(x, 16, text, 17, lit=live and on, color=color)
            x += 18 + len(text) * 13 + 14

        # ---- frequência principal
        if live:
            f = st.freq
            mhz, khz, hz = f // 1_000_000, (f // 1000) % 1000, (f // 10) % 100
            big = f"{mhz:>4d}".replace(" ", " ") + f".{khz:03d}"
            small = f"{hz:02d}"
        else:
            big, small = "----.---", "--"
        end = self._number(30, 62, 70, 128, 20, big, True)
        self._dot(end - 10, 62 + 128 - 6, 6.5, live)
        self._number(end + 6, 62 + 128 - 80, 44, 80, 12, small, True)

        # ---- modo e canal
        self._text(825, 64, st.mode_name if live else "", 46)
        mem = st.vfo == 2 and live
        self._text(825, 140, "CH", 18, lit=mem)
        self._number(870, 132, 26, 48, 8,
                     f"{st.channel:03d}" if mem else "888", lit=mem)

        # ---- medidor (S / PO)
        meter_y, bar_h = 222, 30
        label = "PO" if (st.tx and live) else "S"
        self._text(30, meter_y + 2, label, 22)
        n = 30
        bx0, bx1 = 75, 760
        bw = (bx1 - bx0) / n
        for i in range(n):
            on = live and i < st.smeter
            hh = bar_h * (0.45 + 0.55 * i / (n - 1))
            xa, ya = self._xy(bx0 + i * bw + 2, meter_y + bar_h - hh)
            xb, yb = self._xy(bx0 + (i + 1) * bw - 3, meter_y + bar_h)
            color = self.t["on"] if on else self.t["off"]
            if on and i >= 15 and not st.tx:
                color = self.t["tx"]
            self.create_rectangle(xa, ya, xb, yb, fill=color, outline="")
        scale = ([("1", 1.7), ("3", 5), ("5", 8.3), ("7", 11.7), ("9", 15),
                  ("+20", 20), ("+40", 25), ("+60", 30)] if label == "S" else
                 [("0", 0.5), ("25", 7.5), ("50", 15), ("100", 22.5),
                  ("150", 30)])
        for txt, pos in scale:
            self._text(bx0 + pos * bw - bw / 2, meter_y + bar_h + 6, txt, 14,
                       anchor="n", lit=True)

        # ---- informações secundárias
        self._text(800, 205, "VFO B", 13, lit=live and st.freq_b > 0)
        fb = st.freq_b
        txt = (f"{fb // 1_000_000:>4d}.{(fb // 1000) % 1000:03d}"
               if live and fb else "----.---")
        self._number(800, 225, 18, 32, 6, txt, lit=live and fb > 0)
        if st.rit or st.xit:
            self._text(800, 268, f"RIT {st.rit_offset / 1000:+.2f} kHz", 14,
                       lit=live)
        if st.power is not None and live:
            self._text(800, 292, f"PWR {st.power} W", 14)
        if not live:
            self._text(REF_W / 2, 292, "SEM CONEXÃO COM O RÁDIO", 18,
                       anchor="n")


class DisplayWindow(tk.Toplevel):
    """Janela do display em tempo real: painel moderno ou LCD clássico."""

    def __init__(self, master, on_close=None):
        from . import dashboard, replica
        super().__init__(master)
        self.dashboard = dashboard
        self.replica = replica
        self.title("PT2VHF Prog Tool — TS-2000 em tempo real")
        self.geometry("1270x300")
        self.minsize(480, 240)
        self.on_close_cb = on_close
        self.last = RadioStatus()
        self.view = None
        self.v_style = tk.StringVar(value="replica")
        self.v_theme = tk.StringVar(value="TS-2000 original")
        self.v_top = tk.BooleanVar(value=False)
        self.menu = tk.Menu(self, tearoff=False)
        self.bind("<Button-3>", self._popup)
        self.bind("<Button-2>", self._popup)
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._set_style()

    def _set_style(self) -> None:
        if self.view is not None:
            self.view.destroy()
        if self.v_style.get() == "replica":
            themes = self.replica.THEMES
            if self.v_theme.get() not in themes:
                self.v_theme.set("TS-2000 original")
            self.view = self.replica.Ts2000Replica(self, self.v_theme.get())
        elif self.v_style.get() == "painel":
            themes = self.dashboard.THEMES
            if self.v_theme.get() not in themes:
                self.v_theme.set("Escuro")
            self.view = self.dashboard.Dashboard(self, self.v_theme.get())
        else:
            themes = THEMES
            if self.v_theme.get() not in themes:
                self.v_theme.set("Âmbar (TS-2000)")
            self.view = LcdCanvas(self, self.v_theme.get())
        self.view.pack(fill="both", expand=True)
        self.view.update_status(self.last)
        m = self.menu
        m.delete(0, "end")
        m.add_radiobutton(label="Réplica do display do TS-2000",
                          variable=self.v_style, value="replica",
                          command=self._set_style)
        m.add_radiobutton(label="Painel completo (todos os dados)",
                          variable=self.v_style,
                          value="painel", command=self._set_style)
        m.add_radiobutton(label="LCD clássico", variable=self.v_style,
                          value="lcd", command=self._set_style)
        m.add_separator()
        for name in themes:
            m.add_radiobutton(label=f"Tema: {name}", variable=self.v_theme,
                              value=name, command=lambda: self.view.set_theme(
                                  self.v_theme.get()))
        m.add_separator()
        m.add_checkbutton(label="Sempre no topo", variable=self.v_top,
                          command=lambda: self.attributes(
                              "-topmost", self.v_top.get()))
        m.add_command(label="Tela cheia (F11)",
                      command=self.toggle_fullscreen)

    def _popup(self, event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def toggle_fullscreen(self) -> None:
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def update_status(self, st: RadioStatus) -> None:
        self.last = st
        self.view.update_status(st)

    @property
    def lcd(self):
        return self.view

    def close(self) -> None:
        if self.on_close_cb:
            self.on_close_cb()
        self.destroy()
