"""Tabelas e codificação/decodificação dos comandos CAT do Kenwood TS-2000.

Referências do formato (verificadas contra Hamlib rigs/kenwood/ts2000.c e
CHIRP chirp/drivers/ts2000.py):

    MR P1 P2P3(3) ;                         leitura de memória
    MW P1 P2P3(3) P4..P16 ;                 escrita de memória
    resposta/escrita (após "MR"/"MW"):
      P1  1  0 = dados RX (ou início p/ 290-299), 1 = dados TX (ou fim)
      P2P3 3 número do canal 000-299
      P4  11 frequência em Hz
      P5  1  modo  (1 LSB, 2 USB, 3 CW, 4 FM, 5 AM, 6 FSK, 7 CW-R, 9 FSK-R)
      P6  1  lockout (0/1)
      P7  1  tipo de tom (0 OFF, 1 TONE, 2 CTCSS, 3 DCS)
      P8  2  número do tom   01-39 (base 1)
      P9  2  número CTCSS    01-39 (base 1)
      P10 3  código DCS      000-103 (base 0)
      P11 1  reverse (0/1)
      P12 1  shift (0 simplex, 1 +, 2 -, 3 =)
      P13 9  offset em Hz
      P14 2  passo (índice, depende do modo)
      P15 1  grupo de memória 0-9
      P16 ≤8 nome

    EX P1(3) P2(2) P3(1) P4(1) P5 ;         menus (P5 = valor)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

NUM_MEMORIES = 300          # 000-299
FIRST_PROGRAM_SCAN = 290    # 290-299 = limites de varredura programada
NAME_LEN = 8
MAX_FREQ = 99_999_999_999
MAX_OFFSET = 999_999_999

MODES = {
    1: "LSB", 2: "USB", 3: "CW", 4: "FM", 5: "AM",
    6: "FSK", 7: "CW-R", 9: "FSK-R",
}
MODE_BY_NAME = {v: k for k, v in MODES.items()}

TONE_MODES = {0: "Off", 1: "Tone", 2: "CTCSS", 3: "DCS"}

# 38 tons sub-audíveis + 1750 Hz (índice 1-39 no protocolo)
TONES = [
    67.0, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8,
    97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8,
    136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2,
    192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3, 1750.0,
]

# 104 códigos DCS (índice 000-103 no protocolo)
DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53,
    54, 65, 71, 72, 73, 74, 114, 115, 116, 122, 125, 131,
    132, 134, 143, 145, 152, 155, 156, 162, 165, 172, 174, 205,
    212, 223, 225, 226, 243, 244, 245, 246, 251, 252, 255, 261,
    263, 265, 266, 271, 274, 306, 311, 315, 325, 331, 332, 343,
    346, 351, 356, 364, 365, 371, 411, 412, 413, 423, 431, 432,
    445, 446, 452, 454, 455, 462, 464, 465, 466, 503, 506, 516,
    523, 526, 532, 546, 565, 606, 612, 624, 627, 631, 632, 654,
    662, 664, 703, 712, 723, 731, 732, 734, 743, 754,
]

SHIFTS = {0: "Simplex", 1: "+", 2: "-", 3: "="}

SSB_STEPS = [1.0, 2.5, 5.0, 10.0]                     # LSB/USB/CW/FSK
FM_STEPS = [5.0, 6.25, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 50.0, 100.0]


def steps_for_mode(mode: int) -> list[float]:
    return FM_STEPS if mode in (4, 5) else SSB_STEPS


def is_program_scan(number: int) -> bool:
    return number >= FIRST_PROGRAM_SCAN


class ProtocolError(Exception):
    pass


@dataclass
class Memory:
    number: int
    empty: bool = True
    freq: int = 0               # Hz (RX, ou início para 290-299)
    mode: int = 4
    lockout: bool = False
    tone_mode: int = 0
    tone: int = 8               # índice 1-39 (8 = 88.5 Hz)
    ctcss: int = 8              # índice 1-39
    dcs: int = 0                # índice 0-103
    reverse: bool = False
    shift: int = 0
    offset: int = 0             # Hz
    step: int = 0               # índice em steps_for_mode(mode)
    group: int = 0
    name: str = ""
    # dados TX (MR1/MW1). Para 290-299 é a frequência final da varredura.
    tx_freq: int = 0
    tx_mode: int = 0            # 0 = igual ao RX

    @property
    def split(self) -> bool:
        return (not self.empty and not is_program_scan(self.number)
                and self.tx_freq not in (0, self.freq))

    def copy_to(self, number: int) -> "Memory":
        d = asdict(self)
        d["number"] = number
        return Memory(**d)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        m = cls(**known)
        m.validate()
        return m

    def validate(self) -> None:
        """Lança ValueError se algum campo estiver fora da faixa."""
        if not 0 <= self.number < NUM_MEMORIES:
            raise ValueError(f"Canal {self.number} fora da faixa 000-299")
        if self.empty:
            return
        if not 0 < self.freq <= MAX_FREQ:
            raise ValueError("Frequência inválida")
        if self.mode not in MODES:
            raise ValueError(f"Modo inválido: {self.mode}")
        if self.tx_mode not in (0, *MODES):
            raise ValueError(f"Modo TX inválido: {self.tx_mode}")
        if self.tone_mode not in TONE_MODES:
            raise ValueError("Tipo de tom inválido")
        if not 1 <= self.tone <= len(TONES):
            raise ValueError("Tom inválido")
        if not 1 <= self.ctcss <= len(TONES):
            raise ValueError("CTCSS inválido")
        if not 0 <= self.dcs < len(DCS_CODES):
            raise ValueError("DCS inválido")
        if self.shift not in SHIFTS:
            raise ValueError("Shift inválido")
        if not 0 <= self.offset <= MAX_OFFSET:
            raise ValueError("Offset inválido")
        if not 0 <= self.step < len(steps_for_mode(self.mode)):
            raise ValueError("Passo inválido para o modo")
        if not 0 <= self.group <= 9:
            raise ValueError("Grupo deve ser 0-9")
        if len(self.name) > NAME_LEN:
            raise ValueError(f"Nome com mais de {NAME_LEN} caracteres")
        if any(ord(c) < 0x20 or ord(c) > 0x7e or c == ";" for c in self.name):
            raise ValueError("Nome contém caracteres não permitidos")
        if not 0 <= self.tx_freq <= MAX_FREQ:
            raise ValueError("Frequência TX inválida")


# ---------------------------------------------------------------- memórias

def cmd_read_memory(number: int, tx: bool = False) -> str:
    return f"MR{1 if tx else 0}{number:03d};"


def parse_memory_reply(reply: str) -> tuple[int, int, dict | None]:
    """Decodifica a resposta de MR.

    Retorna (p1, canal, campos) — campos é None se o canal estiver vazio.
    `reply` pode ou não conter o ';' final.
    """
    r = reply.rstrip(";")
    if not r.startswith("MR") or len(r) < 6:
        raise ProtocolError(f"Resposta MR inválida: {reply!r}")
    body = r[2:]
    p1 = int(body[0])
    number = int(body[1:4])
    if len(body) < 39:
        # alguns rádios respondem só o cabeçalho para canal vazio
        return p1, number, None
    try:
        fields = {
            "freq": int(body[4:15]),
            "mode": int(body[15]),
            "lockout": body[16] == "1",
            "tone_mode": int(body[17]),
            "tone": int(body[18:20]),
            "ctcss": int(body[20:22]),
            "dcs": int(body[22:25]),
            "reverse": body[25] == "1",
            "shift": int(body[26]),
            "offset": int(body[27:36]),
            "step": int(body[36:38]),
            "group": int(body[38]),
            "name": body[39:].rstrip(),
        }
    except ValueError as e:
        raise ProtocolError(f"Resposta MR inválida: {reply!r}") from e
    if fields["mode"] == 0 or fields["freq"] == 0:
        return p1, number, None
    return p1, number, fields


def memory_from_replies(number: int, rx_reply: str,
                        tx_reply: str | None) -> Memory:
    p1, num, f = parse_memory_reply(rx_reply)
    if num != number or p1 != 0:
        raise ProtocolError(f"Resposta para canal errado: {rx_reply!r}")
    if f is None:
        return Memory(number=number, empty=True)
    m = Memory(number=number, empty=False, **f)
    # índices fora da faixa (canal com tom desligado pode vir 00) -> padrão
    if not 1 <= m.tone <= len(TONES):
        m.tone = 8
    if not 1 <= m.ctcss <= len(TONES):
        m.ctcss = 8
    if not 0 <= m.dcs < len(DCS_CODES):
        m.dcs = 0
    if not 0 <= m.step < len(steps_for_mode(m.mode)):
        m.step = 0
    if m.mode not in MODES:
        raise ProtocolError(f"Modo desconhecido {m.mode} no canal {number}")
    if tx_reply:
        tp1, tnum, tf = parse_memory_reply(tx_reply)
        same = tf is not None and tf["freq"] == m.freq and \
            tf["mode"] == m.mode and not is_program_scan(number)
        if tnum == number and tp1 == 1 and tf is not None and not same:
            m.tx_freq = tf["freq"]
            m.tx_mode = tf["mode"] if tf["mode"] != m.mode else 0
    return m


def _mem_body(m: Memory, freq: int, mode: int, offset: int) -> str:
    # O TS-2000 recusa canais com tom desligado contendo valores de tom.
    if m.tone_mode == 0:
        tone, ctcss, dcs = 0, 0, 0
    else:
        tone, ctcss, dcs = m.tone, m.ctcss, m.dcs
    return (f"{freq:011d}{mode:1d}{int(m.lockout):1d}{m.tone_mode:1d}"
            f"{tone:02d}{ctcss:02d}{dcs:03d}{int(m.reverse):1d}{m.shift:1d}"
            f"{offset:09d}{m.step:02d}{m.group:1d}{m.name}")


def cmds_write_memory(m: Memory) -> list[str]:
    """Comandos MW para gravar (ou apagar) um canal."""
    m.validate()
    if m.empty:
        return [f"MW0{m.number:03d}{0:035d};"]
    cmds = [f"MW0{m.number:03d}{_mem_body(m, m.freq, m.mode, m.offset)};"]
    if is_program_scan(m.number):
        end = m.tx_freq or m.freq
        cmds.append(f"MW1{m.number:03d}{_mem_body(m, end, m.mode, 0)};")
    elif m.split:
        cmds.append(f"MW1{m.number:03d}"
                    f"{_mem_body(m, m.tx_freq, m.tx_mode or m.mode, 0)};")
    return cmds


# ------------------------------------------------------------------- menus

def menu_key(ex: int, sub: int = 0) -> str:
    return f"{ex:03d}{sub:02d}"


def cmd_read_menu(ex: int, sub: int = 0) -> str:
    return f"EX{ex:03d}{sub:02d}00;"


def cmd_write_menu(ex: int, sub: int, value: str) -> str:
    if not value or not value.isalnum():
        raise ValueError(f"Valor de menu inválido: {value!r}")
    return f"EX{ex:03d}{sub:02d}00{value};"


def parse_menu_reply(reply: str) -> tuple[int, int, str]:
    r = reply.rstrip(";")
    if not r.startswith("EX") or len(r) < 10:
        raise ProtocolError(f"Resposta EX inválida: {reply!r}")
    return int(r[2:5]), int(r[5:7]), r[9:]
