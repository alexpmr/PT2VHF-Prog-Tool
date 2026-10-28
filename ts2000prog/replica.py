"""Réplica do display do painel do TS-2000 (layout do manual do rádio).

Lado MAIN: medidores (S/PWR em cima; ALC/SWR/COMP ou FILTER embaixo),
indicadores (PTT, CTRL, ATT, PRE, DCS, C, T, M.B.C., A.NOTCH, N.R.1/2,
AGC, NB, +/−, RX AT TX, EXT ANT 1 2...), canal de memória, frequência,
◄A► ◄B► ◄M►, SPLIT, F LOCK A e a caixa de texto (modo).
Lado SUB: S-meter, RIT/XIT, VFO B (ou offset do RIT/XIT) e caixa de texto.
Indicadores sem leitura CAT disponível ficam apagados ("fantasma").
"""

from __future__ import annotations

import sys

from .lcd import LcdCanvas
from .status import SSB_HIGHCUT, SSB_LOWCUT, TX_METERS, RadioStatus, \
    extra_int

REF_W, REF_H = 1400, 250
MONO = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"

THEMES = {
    "TS-2000 original": {"bg": "#f7a52a", "on": "#4a1400", "off": "#eb9a2c",
                         "tx": "#a30000", "frame": "#2b2c30",
                         "bezel": "#3a3c41", "label": "#c9ccd2"},
    "Noturno": {"bg": "#1a0d00", "on": "#ffb03a", "off": "#2e1906",
                "tx": "#ff5a3c", "frame": "#111114", "bezel": "#1d1e22",
                "label": "#7d8088"},
}


class Ts2000Replica(LcdCanvas):
    def __init__(self, master, theme: str = "TS-2000 original", **kw):
        super().__init__(master, **kw)
        self.theme_name = theme

    @property
    def t(self) -> dict:
        return THEMES[self.theme_name]

    # ------------------------------------------------------- primitivas
    def _ann(self, x, y, text, on, size=13, color=None):
        self._text(x, y, text, size, lit=on, color=color if on else None)

    def _inv(self, x, y, text, on, size=12):
        """Indicador invertido (fundo escuro, letra clara): PTT, RX, TX..."""
        w = 8 + len(text) * size * 0.72
        x0, y0 = self._xy(x, y)
        x1, y1 = self._xy(x + w, y + size * 1.45)
        self.create_rectangle(x0, y0, x1, y1, outline="",
                              fill=self.t["on"] if on else self.t["off"])
        self._text(x + w / 2, y + size * 0.72, text, size, anchor="center",
                   color=self.t["bg"])
        return x + w + 3

    def _boxed(self, x, y, text, on, size=11):
        """Indicador com moldura arredondada: CTRL."""
        w = 10 + len(text) * size * 0.72
        c = self.t["on"] if on else self.t["off"]
        x0, y0 = self._xy(x, y)
        x1, y1 = self._xy(x + w, y + size * 1.5)
        self.create_rectangle(x0, y0, x1, y1, outline=c,
                              width=max(1.4 * self.k, 1))
        self._text(x + w / 2, y + size * 0.75, text, size, lit=on,
                   anchor="center")

    def _bars(self, x, y, w, n, value, h_lo, h_hi, rise=0.0):
        """Barra de segmentos; altura cresce de h_lo a h_hi e sobe `rise`."""
        bw = w / n
        for i in range(n):
            f = i / (n - 1)
            on = self.status.connected and i < value
            hh = h_lo + (h_hi - h_lo) * f
            base = y - rise * f * f
            xa, ya = self._xy(x + i * bw + 1, base - hh)
            xb, yb = self._xy(x + (i + 1) * bw - 1.2, base)
            self.create_rectangle(xa, ya, xb, yb, outline="",
                                  fill=self.t["on"] if on else self.t["off"])

    def _scale(self, x, y, w, marks, size=10, rise=0.0):
        for lab, pos in marks:
            f = pos / 30
            self._text(x + w * f, y - rise * f * f, lab, size, lit=True,
                       anchor="s", bold=False)

    def _matrix(self, x0, y0, x1, y1, text):
        """Caixa de texto em matriz de pontos (modo / nome)."""
        a, b = self._xy(x0, y0)
        c, d = self._xy(x1, y1)
        self.create_rectangle(a, b, c, d, outline=self.t["off"],
                              width=max(1.4 * self.k, 1))
        if text:
            self._text((x0 + x1) / 2, (y0 + y1) / 2, text, 24,
                       anchor="center", color=self.t["on"])

    def _freq_digits(self, x, y, w, h, gap, hz, live):
        """Frequência com resolução de 10 Hz: '  14.200.00'."""
        if live and hz:
            v = f"{hz // 10:>9d}"
            txt = f"{v[:4]}.{v[4:7]}.{v[7:]}".replace(" .", "  ")
        else:
            txt = "    .   .  "
        return self._number(x, y, w, h, gap, txt, True)

    # ---------------------------------------------------------- desenho
    def redraw(self) -> None:
        self.delete("all")
        W, H = self.winfo_width(), self.winfo_height()
        if W < 80 or H < 40:
            return
        self.k = min(W / REF_W, H / REF_H)
        self.ox = (W - REF_W * self.k) / 2
        self.oy = (H - REF_H * self.k) / 2
        t = self.t
        self.configure(bg=t["frame"])
        a, b = self._xy(0, 0)
        c, d = self._xy(REF_W, REF_H)
        self.create_rectangle(a, b, c, d, fill=t["bezel"], outline="")
        self._text(REF_W - 190, 10, "HF/VHF/UHF ALL MODE MULTI BANDER", 11,
                   color=t["label"], anchor="ne", bold=False)
        self._text(REF_W - 40, 10, "TS-2000", 11, color=t["label"],
                   anchor="ne")
        a, b = self._xy(14, 32)
        c, d = self._xy(REF_W - 14, REF_H - 30)
        self.create_rectangle(a, b, c, d, fill=t["bg"], outline="#151517",
                              width=max(3 * self.k, 1))
        self._text(560, REF_H - 24, "MAIN", 12, color=t["label"])
        self._text(1180, REF_H - 24, "SUB", 12, color=t["label"])
        st = self.status
        live = st.connected
        self._meters(st, live)
        self._main(st, live)
        self._sub(st, live)
        if not live:
            self._text(REF_W / 2, REF_H - 24, "SEM CONEXÃO COM O RÁDIO", 12,
                       color=t["label"], anchor="n")

    def _meters(self, st: RadioStatus, live: bool) -> None:
        x, w = 50, 300
        tx = live and st.tx
        # escala S (curva para cima, como no painel)
        self._text(26, 74, "S", 11, lit=True, bold=False)
        self._scale(x, 72, w, [("1", 1.7), ("3", 5), ("5", 8.3),
                               ("7", 11.7), ("9", 15), ("20", 20),
                               ("40", 25), ("60dB", 30)], rise=10)
        self._bars(x, 100, w, 30, st.smeter if live else 0, 9, 12, rise=10)
        # escala PWR/ALC (TX)
        self._text(24, 116, "PWR", 9, lit=True, bold=False)
        self._text(24, 128, "ALC", 9, lit=True, bold=False)
        self._scale(x, 118, w, [("10", 5), ("25", 12), ("50", 18),
                                ("100W%", 29)], size=9)
        # barra de baixo: medidor de TX, ou largura do filtro em RX
        if tx:
            raw = st.extra.get("txmeter", "")
            low = extra_int(st, "txmeter", 0) % 10000 if raw else 0
            kind = TX_METERS.get(raw[:1], "ALC")
        else:
            low = self._filter_segments(st) if live else 0
            kind = ""
        self._bars(x, 150, w, 30, low, 14, 14)
        self._text(18, 152, "SWR", 9, lit=tx and kind == "SWR", bold=False)
        self._text(14, 163, "COMP1", 9, lit=tx and kind == "COMP",
                   bold=False)
        self._scale(x, 170, w, [("1.5", 3), ("10", 7), ("2", 9), ("3", 15),
                                ("20dB", 22), ("∞", 30)], size=9)
        self._text(x + w * 0.5, 172, "— FILTER —", 9, lit=live and not tx,
                   anchor="n", bold=False)
        # RX AT TX / EXT ANT 1 2
        tuner = st.extra.get("tuner", "")
        nx = self._inv(40, 196, "RX", live and tuner[:1] == "1")
        self._text(nx, 196, "AT", 12, lit=live and (tuner[:1] == "1" or
                                                     tuner[1:2] == "1"))
        nx = self._inv(nx + 26, 196, "TX", live and tuner[1:2] == "1")
        ant = st.extra.get("ant", "")
        nx = self._inv(nx + 16, 196, "EXT", False)
        self._text(nx, 196, "ANT", 12, lit=live and ant in ("1", "2"))
        nx = self._inv(nx + 36, 196, "1", live and ant == "1")
        self._inv(nx, 196, "2", live and ant == "2")

    def _filter_segments(self, st: RadioStatus) -> int:
        lo, hi = extra_int(st, "lowcut"), extra_int(st, "highcut")
        if st.mode in (1, 2) and lo is not None and hi is not None and \
                lo < len(SSB_LOWCUT) and hi < len(SSB_HIGHCUT):
            return round((SSB_HIGHCUT[hi] - SSB_LOWCUT[lo]) / 5000 * 30)
        width = extra_int(st, "width")
        return round(width / 6000 * 30) if width else 0

    def _main(self, st: RadioStatus, live: bool) -> None:
        on = live
        agc = extra_int(st, "agc")
        bc = extra_int(st, "bc", 0)
        # linha 1
        self._ann(372, 44, "MHz", False)
        self._inv(424, 44, "PTT", on and st.tx)
        self._ann(478, 44, "ATT", on and st.att)
        self._ann(522, 44, "PRE", on and st.preamp)
        self._ann(566, 44, "DCS", on and st.tone_mode == 3)
        self._ann(614, 44, "C", on and st.tone_mode == 2)
        self._ann(630, 44, "T", on and st.tone_mode == 1)
        self._ann(652, 44, "M.", on and bc == 2)
        self._ann(670, 44, "B.C.", on and bc != 0)
        self._ann(712, 44, "A.NOTCH", False)
        self._ann(792, 44, "N.R.", on and st.nr != 0)
        self._inv(828, 44, "1", on and st.nr == 1)
        self._inv(843, 44, "2", on and st.nr == 2)
        self._ann(874, 44, "TRACE", False)
        self._inv(930, 44, "R", False)
        # linha 2
        self._ann(372, 66, "ALT", False)
        self._boxed(424, 66, "CTRL", on)
        self._ann(478, 66, "TNC", False)
        self._ann(526, 66, "+", on and st.shift == 1)
        self._ann(538, 66, "−", on and st.shift == 2)
        self._ann(550, 66, "=", on and st.shift == 3)
        self._ann(570, 66, "(R)", False)
        self._ann(604, 66, "AGC", on and agc not in (0, None))
        self._ann(652, 66, "NB", on and st.nb)
        self._ann(712, 66, "FINE", False)
        self._ann(766, 66, "EQ", False)
        self._ann(838, 66, "★", False)
        self._ann(874, 66, "P.C.T.", False)
        # canal de memória (pequeno) e frequência principal
        mem = on and st.vfo == 2
        self._ann(372, 92, "M.CH", mem, size=15)
        self._number(372, 118, 14, 30, 4,
                     f"{st.channel:03d}" if mem else "   ", True)
        end = self._freq_digits(432, 96, 36, 66, 9, st.freq, on)
        # SPLIT, ◄A► ◄B► ◄M►, F LOCK A
        x = end + 2
        self._ann(x, 90, "SPLIT", on and st.split)
        self._ann(x + 4, 110, "◄A►", on and st.vfo == 0, size=14)
        self._ann(x + 4, 130, "◄B►", on and st.vfo == 1, size=14)
        self._ann(x + 4, 150, "◄M►", on and st.vfo == 2, size=14)
        lock = on and st.extra.get("lock", "0")[:1] not in ("0", "")
        self._inv(x - 20, 196, "F", lock)
        self._ann(x - 4, 196, "LOCK", lock)
        self._inv(x + 48, 196, "A", lock)
        # AUTO e caixa de texto (modo)
        self._ann(372, 172, "AUTO", False)
        self._matrix(432, 178, 860, 214, st.mode_name if on else "")
        if on and st.tx:
            self._text(866, 186, "TX", 14, color=self.t["tx"])

    def _sub(self, st: RadioStatus, live: bool) -> None:
        on = live
        x0 = 1020
        self._ann(x0 - 46, 44, "SATL", False, size=11)
        self._inv(x0, 44, "PTT", False)
        self._ann(x0 + 54, 44, "ATT", False)
        self._ann(x0 + 98, 44, "PRE", False)
        self._ann(x0 + 142, 44, "DCS", False)
        self._ann(x0 + 190, 44, "C T", False)
        self._ann(x0 + 230, 44, "N.R.", False)
        self._ann(x0 + 290, 44, "PKT", False)
        self._boxed(x0, 66, "CTRL", False)
        self._ann(x0 + 54, 66, "TNC", False)
        self._ann(x0 + 98, 66, "+=", False)
        self._ann(x0 + 142, 66, "(R)", False)
        self._ann(x0 + 190, 66, "★", False)
        self._ann(x0 + 290, 66, "PC", False)
        self._ann(x0 + 54, 86, "XIT", on and st.xit, size=15)
        self._ann(x0 + 98, 86, "RIT", on and st.rit, size=15)
        sub = extra_int(st, "smeter_sub")
        self._text(x0 + 142, 92, "S", 8, lit=True, bold=False)
        self._bars(x0 + 152, 108, 140, 15, sub if on and sub else 0, 4, 16,
                   rise=0)
        self._ann(x0 - 46, 92, "M.CH", False, size=15)
        if on and (st.rit or st.xit):
            off = st.rit_offset
            txt = f"{'-' if off < 0 else ' '}{abs(off) / 1000:7.2f}"
            self._number(x0 + 6, 120, 22, 42, 6, txt, True)
        else:
            self._freq_digits(x0 - 14, 120, 22, 42, 6, st.freq_b, on)
        self._matrix(x0 - 14, 178, REF_W - 40, 214,
                     "VFO B" if on and not (st.rit or st.xit) else
                     ("RIT/XIT" if on else ""))
