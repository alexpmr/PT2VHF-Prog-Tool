"""Réplica do display do painel do TS-2000.

Mesmo arranjo do rádio: barra do S-meter em arco com escala S1…60 dB,
barras PWR/ALC e FILTER à esquerda; frequência principal no centro com
modo e indicadores; lado SUB à direita (VFO B, ou o offset do RIT/XIT
quando ligado, como o rádio faz). Segmentos apagados ficam "fantasma".
"""

from __future__ import annotations

from .lcd import LcdCanvas
from .status import SSB_HIGHCUT, SSB_LOWCUT, RadioStatus, extra_int

REF_W, REF_H = 1270, 300

THEMES = {
    "TS-2000 original": {"bg": "#f7a52a", "on": "#5c1800", "off": "#eb9622",
                         "tx": "#a30000", "frame": "#2b2c30",
                         "bezel": "#3a3c41", "label": "#c9ccd2"},
    "Noturno": {"bg": "#1a0d00", "on": "#ffb03a", "off": "#2c1704",
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

    def _seg_text(self, x, y, text, size, lit=True, anchor="nw"):
        """Letras do display (modo etc.) em fonte condensada."""
        self._text(x, y, text, size, lit=lit, anchor=anchor)

    def _box_label(self, x, y, text, lit):
        """Indicador com moldura (PTT, CTRL)."""
        color = self.t["on"] if lit else self.t["off"]
        w = 14 + len(text) * 11
        x0, y0 = self._xy(x, y)
        x1, y1 = self._xy(x + w, y + 22)
        self.create_rectangle(x0, y0, x1, y1, outline=color,
                              width=max(1.5 * self.k, 1))
        self._text(x + w / 2, y + 11, text, 13, lit=lit, anchor="center")

    def _meter(self, x, y, w, n, value, arc=False, h0=10, h1=26):
        """Barra de segmentos; com arc=True a altura cresce como no rádio."""
        bw = w / n
        for i in range(n):
            on = self.status.connected and i < value
            hh = (h0 + (h1 - h0) * (i / (n - 1)) ** 1.4) if arc else h0
            yy = y - (i / (n - 1)) ** 2 * 10 if arc else y
            xa, ya = self._xy(x + i * bw + 1.2, yy - hh)
            xb, yb = self._xy(x + (i + 1) * bw - 1.2, yy)
            self.create_rectangle(xa, ya, xb, yb, outline="",
                                  fill=self.t["on"] if on else self.t["off"])

    # ------------------------------------------------------------ desenho
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
        # moldura e janela do LCD
        bx0, by0 = self._xy(0, 0)
        bx1, by1 = self._xy(REF_W, REF_H)
        self.create_rectangle(bx0, by0, bx1, by1, fill=t["bezel"],
                              outline="")
        self._text(REF_W - 170, 14, "HF/VHF/UHF ALL MODE MULTI BANDER",
                   12, color=t["label"], anchor="ne")
        self._text(REF_W - 70, 14, "TS-2000", 12, color=t["label"],
                   anchor="ne")
        lx0, ly0 = self._xy(18, 40)
        lx1, ly1 = self._xy(REF_W - 18, REF_H - 40)
        self.create_rectangle(lx0, ly0, lx1, ly1, fill=t["bg"],
                              outline="#1b1b1d", width=max(3 * self.k, 1))
        self._text(370, REF_H - 30, "MAIN", 13, color=t["label"])
        self._text(960, REF_H - 30, "SUB", 13, color=t["label"])

        st = self.status
        live = st.connected
        self._left_meters(st, live)
        self._main(st, live)
        self._sub(st, live)

    def _left_meters(self, st: RadioStatus, live: bool) -> None:
        # escala do S-meter (como no painel: S-1-3-5-7-9-20-40-60dB)
        x0, w = 66, 280
        scale = [("S", 0), ("1", 1.7), ("3", 5), ("5", 8.3), ("7", 11.7),
                 ("9", 15), ("20", 20), ("40", 25), ("60dB", 30)]
        for lab, pos in scale:
            self._text(x0 + w * pos / 30, 62 - (pos / 30) ** 2 * 10, lab,
                       12, lit=True, anchor="n")
        tx = st.tx and live
        self._meter(x0, 116, w, 30, 0 if tx else st.smeter, arc=True)
        # PWR (durante TX) e ALC
        for lab, pos in (("PWR", -1), ("10", 4), ("25", 9), ("50", 15),
                         ("100W", 29)):
            if pos < 0:
                self._text(28, 124, lab, 10, lit=True)
            else:
                self._text(x0 + w * pos / 30, 124, lab, 10, lit=True,
                           anchor="n")
        self._meter(x0, 156, w, 30, st.smeter if tx else 0, h0=12)
        self._text(28, 170, "ALC", 10, lit=True)
        alc = extra_int(st, "txmeter", 0) % 10000 if tx else 0
        self._meter(x0, 176, w, 30, alc, h0=8)
        # FILTER: largura proporcional ao filtro DSP
        lo, hi = extra_int(st, "lowcut"), extra_int(st, "highcut")
        nseg = 0
        if live and lo is not None and hi is not None and \
                lo < len(SSB_LOWCUT) and hi < len(SSB_HIGHCUT):
            nseg = round((SSB_HIGHCUT[hi] - SSB_LOWCUT[lo]) / 5000 * 20)
        elif live:
            nseg = 12
        self._text(x0 + 150, 204, "— FILTER —", 11, lit=True,
                   anchor="n")
        start = (20 - nseg) // 2
        for i in range(20):
            on = start <= i < start + nseg
            xa, ya = self._xy(x0 + 30 + i * 12, 226)
            xb, yb = self._xy(x0 + 30 + i * 12 + 9, 232)
            self.create_rectangle(xa, ya, xb, yb, outline="",
                                  fill=self.t["on"] if on else
                                  self.t["off"])
        ant = st.extra.get("ant", "1") or "1"
        self._text(300, 236, f"ANT{ant}", 15, lit=live)

    def _main(self, st: RadioStatus, live: bool) -> None:
        t = self.t
        self._box_label(400, 58, "PTT", live and st.tx)
        self._box_label(400, 86, "CTRL", live)
        self._text(470, 58, "PRE", 13, lit=live and st.preamp)
        self._text(470, 80, "ATT", 13, lit=live and st.att)
        self._text(540, 80, "AGC", 13, lit=live and extra_int(st, "agc")
                   not in (0, None))
        self._text(610, 80, "NB", 13, lit=live and st.nb)
        self._text(650, 80, f"NR{st.nr or 1}", 13, lit=live and st.nr != 0)
        self._text(705, 80, "PROC", 13,
                   lit=live and st.extra.get("proc", "")[:1] == "1")
        self._text(765, 80, "VOX", 13,
                   lit=live and st.extra.get("vox", "")[:1] == "1")
        # frequência principal: 14.200.00
        if live:
            f = st.freq
            mhz = f // 1_000_000
            txt = f"{mhz:>4d}.{(f // 1000) % 1000:03d}.{(f // 10) % 100:02d}"
        else:
            txt = "----.---.--"
        end = self._number(470, 112, 36, 74, 10, txt, True)
        if live:
            vfo = {0: "◄A", 1: "◄B"}.get(st.vfo, "M.CH")
            self._text(end + 4, 160, vfo, 18, color=t["on"])
        # modo e indicadores da linha de baixo
        self._text(660, 210, st.mode_name if live else "", 34,
                   color=t["tx"] if live and st.tx else None, anchor="n")
        self._text(470, 220, "SPLIT", 13, lit=live and st.split)
        tone = {1: "T", 2: "CT", 3: "DCS"}.get(st.tone_mode, "T")
        self._text(540, 220, tone, 13, lit=live and st.tone_mode != 0)
        self._text(780, 220, "SCAN", 13, lit=live and st.scan)
        if live and st.vfo == 2:
            self._number(860, 206, 18, 32, 6, f"{st.channel:03d}", True)

    def _sub(self, st: RadioStatus, live: bool) -> None:
        self._text(1010, 58, "PRE", 13, lit=False)
        self._text(970, 80, "TNC", 13, lit=False)
        self._text(1060, 80, "RIT", 13, lit=live and st.rit)
        self._text(1100, 80, "XIT", 13, lit=live and st.xit)
        if live and (st.rit or st.xit):
            off = st.rit_offset
            txt = f"{'-' if off < 0 else ' '}{abs(off) / 1000:5.2f}"
        elif live and st.freq_b:
            f = st.freq_b
            txt = (f"{f // 1_000_000:>4d}.{(f // 1000) % 1000:03d}."
                   f"{(f // 10) % 100:02d}")
        else:
            txt = "----.---.--"
        self._number(965, 132, 20, 44, 6, txt, True)
        self._text(1060, 212, "VFO B" if live and not (st.rit or st.xit)
                   else "", 20, lit=live, anchor="n")
