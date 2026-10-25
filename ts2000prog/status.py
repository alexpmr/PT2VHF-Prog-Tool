"""Leitura do estado do TS-2000 em tempo real (para o display).

Campos do IF (posições na resposta, contando "IF" como 0-1), conforme
Hamlib rigs/kenwood/kenwood.c:
    2-12  frequência (Hz, 11 dígitos)     28  0 = RX, 1 = TX
    13-17 passo / não usado               29  modo
    18-22 offset RIT/XIT (±9999 Hz)       30  0 = VFO A, 1 = VFO B, 2 = memória
    23    RIT ligado                      31  varredura
    24    XIT ligado                      32  split
    25-27 canal de memória                33  0 off, 1 tone, 2 CTCSS, 3 DCS
    34-35 número do tom                   36  shift
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import MODES


@dataclass
class RadioStatus:
    connected: bool = False
    freq: int = 0
    rit_offset: int = 0
    rit: bool = False
    xit: bool = False
    channel: int = 0
    tx: bool = False
    mode: int = 0
    vfo: int = 0                # 0 A, 1 B, 2 memória
    scan: bool = False
    split: bool = False
    tone_mode: int = 0
    shift: int = 0
    smeter: int = 0             # 0-30 (S9 ~ 15)
    freq_b: int = 0
    power: int | None = None    # W (PC)
    preamp: bool = False
    att: bool = False
    nb: bool = False
    nr: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def mode_name(self) -> str:
        return MODES.get(self.mode, "")


def parse_if(reply: str, st: RadioStatus) -> None:
    r = reply.rstrip(";")
    if not r.startswith("IF") or len(r) < 37:
        raise ValueError(f"Resposta IF inválida: {reply!r}")
    st.freq = int(r[2:13])
    off = r[18:23].strip()
    try:
        st.rit_offset = int(off) if off else 0
    except ValueError:
        st.rit_offset = 0
    st.rit = r[23] == "1"
    st.xit = r[24] == "1"
    ch = r[25:28].strip()
    st.channel = int(ch) if ch.isdigit() else 0
    st.tx = r[28] == "1"
    st.mode = int(r[29]) if r[29].isdigit() else 0
    st.vfo = int(r[30]) if r[30].isdigit() else 0
    st.scan = r[31] not in ("0", " ")
    st.split = r[32] == "1"
    st.tone_mode = int(r[33]) if r[33].isdigit() else 0
    st.shift = int(r[36]) if len(r) > 36 and r[36].isdigit() else 0


def _digits(reply: str, prefix_len: int) -> int:
    s = reply.rstrip(";")[prefix_len:]
    return int(s) if s.isdigit() else 0


def parse_sm(reply: str) -> int:
    """SM0 -> 'SM0nnnn;' (0-30)."""
    return _digits(reply, 3)


def parse_freq(reply: str) -> int:
    return _digits(reply, 2)
