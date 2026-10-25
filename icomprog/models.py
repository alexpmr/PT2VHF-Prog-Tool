"""Mapas de memória (imagem de clonagem) do Icom ID-51A Plus2 e ID-880H.

Os layouts foram levantados a partir dos drivers do CHIRP
(chirp/drivers/id31.py, id51plus.py e id880.py, GPLv3). O código abaixo
edita somente os campos conhecidos de cada registro e preserva os demais
bits da imagem, de modo que configurações não suportadas continuam intactas
ao clonar de volta para o rádio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5,
    203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
]

DTCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54,
    65, 71, 72, 73, 74, 114, 115, 116, 122, 125, 131,
    132, 134, 143, 145, 152, 155, 156, 162, 165, 172, 174,
    205, 212, 223, 225, 226, 243, 244, 245, 246, 251, 252,
    255, 261, 263, 265, 266, 271, 274, 306, 311, 315, 325,
    331, 332, 343, 346, 351, 356, 364, 365, 371, 411, 412,
    413, 423, 431, 432, 445, 446, 452, 454, 455, 462, 464,
    465, 466, 503, 506, 516, 523, 526, 532, 546, 565, 606,
    612, 624, 627, 631, 632, 654, 662, 664, 703, 712, 723,
    731, 732, 734, 743, 754,
]

DUPLEX = {0: "Simplex", 1: "-", 2: "+"}
DTCS_POLARITY = {0: "NN", 1: "NR", 2: "RN", 3: "RR"}
SKIPS = {"": "—", "S": "Skip", "P": "P.Skip"}
TONE_SHORT = {0: "", 1: "Tone", 2: "TSQL", 3: "TSQL", 4: "DTCS", 5: "DTCS",
              6: "TSQL-R", 7: "DTCS-R"}
CALL_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/ ")


@dataclass
class IcomMemory:
    number: int
    empty: bool = True
    freq: int = 0
    offset: int = 0
    duplex: int = 0
    mode: int = 0               # código bruto do modo
    name: str = ""
    tmode: int = 0              # código bruto 0-7
    rtone: int = 8              # índice em TONES (8 = 88.5)
    ctone: int = 8
    dtcs: int = 0               # índice em DTCS_CODES
    dtcs_pol: int = 0
    step: int = 0               # índice bruto do passo
    skip: str = ""
    bank: int | None = None     # 0-25 (A-Z)
    bank_index: int = 0
    urcall: str = "CQCQCQ"
    rpt1: str = ""
    rpt2: str = ""
    dv_code: int = 0
    dsql: int = 0               # ID-51: 0 off, 1 DSQL, 2 CSQL

    def to_dict(self) -> dict:
        return asdict(self)

    def copy_to(self, number: int) -> "IcomMemory":
        return IcomMemory(**{**asdict(self), "number": number})


# ------------------------------------------------------------ utilidades

def _u16(b: bytes | bytearray, o: int) -> int:
    return (b[o] << 8) | b[o + 1]


def _put16(b: bytearray, o: int, v: int) -> None:
    b[o] = (v >> 8) & 0xFF
    b[o + 1] = v & 0xFF


def _u24(b: bytes | bytearray, o: int) -> int:
    return (b[o] << 16) | (b[o + 1] << 8) | b[o + 2]


def _put24(b: bytearray, o: int, v: int) -> None:
    b[o:o + 3] = v.to_bytes(3, "big")


def decode_call(raw: bytes | bytearray) -> str:
    """7 bytes -> 8 caracteres de 7 bits (empacotados MSB primeiro)."""
    bits = int.from_bytes(raw, "big")
    chars = [(bits >> (49 - 7 * i)) & 0x7F for i in range(8)]
    return "".join(chr(c) if 32 <= c < 127 else " " for c in chars).rstrip()


def encode_call(call: str) -> bytes:
    call = call.upper().ljust(8)[:8]
    bits = 0
    for c in call:
        bits = (bits << 7) | (ord(c) & 0x7F)
    return bits.to_bytes(7, "big")


def _text(raw: bytes | bytearray) -> str:
    return "".join(chr(c) if 32 <= c < 127 else " " for c in raw).rstrip()


def _bit(img, base: int, n: int) -> bool:
    return bool(img[base + n // 8] & (1 << (n % 8)))


def _setbit(img: bytearray, base: int, n: int, on: bool) -> None:
    if on:
        img[base + n // 8] |= 1 << (n % 8)
    else:
        img[base + n // 8] &= ~(1 << (n % 8)) & 0xFF


# ================================================================ modelos

class IcomModel:
    key = ""
    name = ""
    model_id = b"\x00\x00\x00\x00"
    memsize = 0
    ranges: list[tuple[int, int, int]] = []
    endframe = b""
    raw_frames = False
    highbit_flip = False
    hispeed = True
    num_memories = 0
    rec_size = 0
    name_len = 8
    num_banks = 26
    bank_name_len = 6
    bank_names_at = 0
    modes: dict[int, str] = {}
    edit_modes: list[int] = []
    steps: list[float | None] = []
    bands: list[tuple[int, int]] = []
    tmode_labels: dict[int, str] = {}
    default_tsql = 3
    default_dtcs = 5
    icf_meta: dict = {}
    icf_recordsize = 16

    # ---- interface pública
    def decode(self, img, n: int) -> IcomMemory:
        raise NotImplementedError

    def encode(self, img: bytearray, m: IcomMemory) -> None:
        raise NotImplementedError

    def bank_name(self, img, i: int) -> str:
        o = self.bank_names_at + i * self.bank_name_len
        return _text(img[o:o + self.bank_name_len])

    def set_bank_name(self, img: bytearray, i: int, name: str) -> None:
        o = self.bank_names_at + i * self.bank_name_len
        img[o:o + self.bank_name_len] = \
            name.ljust(self.bank_name_len)[:self.bank_name_len].encode("ascii")

    def validate(self, m: IcomMemory) -> None:
        if not 0 <= m.number < self.num_memories:
            raise ValueError("Canal fora da faixa")
        if m.empty:
            return
        if not any(lo <= m.freq <= hi for lo, hi in self.bands):
            faixas = ", ".join(f"{lo / 1e6:g}-{hi / 1e6:g}"
                               for lo, hi in self.bands)
            raise ValueError(f"Frequência fora das faixas do rádio "
                             f"({faixas} MHz)")
        if m.mode not in self.modes:
            raise ValueError("Modo inválido")
        if not (0 <= m.step < len(self.steps) and self.steps[m.step]):
            raise ValueError("Passo inválido")
        if len(m.name) > self.name_len:
            raise ValueError(f"Nome com mais de {self.name_len} caracteres")
        if any(not 32 <= ord(c) < 127 for c in m.name):
            raise ValueError("Nome contém caracteres não ASCII")
        for label, call in (("URCALL", m.urcall), ("RPT1", m.rpt1),
                            ("RPT2", m.rpt2)):
            if len(call) > 8 or not set(call.upper()) <= CALL_CHARS:
                raise ValueError(f"{label} inválido (até 8 caracteres "
                                 "A-Z, 0-9, /)")
        if not 0 <= m.dv_code <= 99:
            raise ValueError("Código digital deve ser 0-99")
        if m.bank is not None and not 0 <= m.bank < self.num_banks:
            raise ValueError("Banco inválido")
        if not 0 <= m.bank_index <= 99:
            raise ValueError("Índice no banco deve ser 0-99")
        self._encode_freq(m.freq)
        self._encode_freq(m.offset)

    def blank_image(self) -> bytearray:
        """Imagem vazia (apenas para o simulador e testes)."""
        img = bytearray(self.memsize)
        for n in range(self.num_memories):
            self._mark_empty(img, n)
        for i in range(self.num_banks):
            self.set_bank_name(img, i, f"BANK-{chr(65 + i)}")
        return img

    # ---- auxiliares para subclasses
    def _encode_freq(self, hz: int) -> tuple[int, int]:
        raise NotImplementedError

    def _mark_empty(self, img: bytearray, n: int) -> None:
        raise NotImplementedError


class ID51Plus2(IcomModel):
    key = "id51plus2"
    name = "ID-51A Plus2"
    model_id = b"\x33\x90\x00\x03"
    memsize = 0x1FB40
    ranges = [(0x00000, 0x1FB40, 32)]
    endframe = b"Icom Inc.DA"
    raw_frames = True
    highbit_flip = True
    num_memories = 500
    rec_size = 49
    name_len = 16
    bank_name_len = 16
    bank_names_at = 0x6FD0
    USED, SKIP, PSKIP, BANKS = 0x6A40, 0x6A86, 0x6ACB, 0x6B40
    modes = {0: "FM", 1: "NFM", 3: "AM", 5: "DV"}
    edit_modes = [0, 1, 3, 5]
    steps = [5.0, 6.25, None, None, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0,
             50.0, 100.0, 125.0, 200.0]
    bands = [(108_000_000, 174_000_000), (380_000_000, 479_000_000)]
    tmode_labels = {0: "Off", 1: "Tone", 2: "TSQL (cód. 2)", 3: "TSQL",
                    4: "DTCS (cód. 4)", 5: "DTCS", 6: "TSQL-R", 7: "DTCS-R"}
    default_tsql, default_dtcs = 3, 5
    icf_meta = {"Comment": "", "MapRev": 1, "EtcData": 0x400001}
    icf_recordsize = 32

    def decode(self, img, n: int) -> IcomMemory:
        m = IcomMemory(number=n)
        if _bit(img, self.USED, n):
            return m
        o = n * self.rec_size
        r = img[o:o + self.rec_size]
        f = _u24(r, 0)
        mult = 6250 if f & 0x200000 else 5000
        omult = 6250 if f & 0x040000 else 5000
        w = _u16(r, 5)
        bank = img[self.BANKS + 2 * n] & 0x1F
        m.empty = False
        m.freq = (f & 0x3FFFF) * mult
        m.offset = _u16(r, 3) * omult
        m.rtone = min(w >> 10, len(TONES) - 1)
        m.ctone = min((w >> 4) & 0x3F, len(TONES) - 1)
        m.mode = w & 0x07
        m.dtcs = min(r[7], len(DTCS_CODES) - 1)
        m.step = r[8] >> 4
        m.dsql = (r[8] >> 2) & 0x03
        m.tmode = (r[10] >> 4) & 0x07
        m.duplex = (r[10] >> 2) & 0x03
        m.dtcs_pol = r[10] & 0x03
        m.name = _text(r[11:27])
        m.dv_code = r[27] & 0x7F
        m.urcall = decode_call(r[28:35])
        m.rpt1 = decode_call(r[35:42])
        m.rpt2 = decode_call(r[42:49])
        if _bit(img, self.PSKIP, n):
            m.skip = "P"
        elif _bit(img, self.SKIP, n):
            m.skip = "S"
        m.bank = None if bank == 0x1F else bank
        m.bank_index = img[self.BANKS + 2 * n + 1]
        return m

    def _encode_freq(self, hz: int) -> tuple[int, int]:
        if hz % 5000 == 0:
            return hz // 5000, 0
        if hz % 6250 == 0:
            return hz // 6250, 1
        raise ValueError(f"{hz / 1e6:.6f} MHz não é múltiplo de 5 ou "
                         "6,25 kHz")

    def _mark_empty(self, img: bytearray, n: int) -> None:
        _setbit(img, self.USED, n, True)
        b = self.BANKS + 2 * n
        img[b] = (img[b] & 0xE0) | 0x1F

    def encode(self, img: bytearray, m: IcomMemory) -> None:
        self.validate(m)
        n = m.number
        if m.empty:
            self._mark_empty(img, n)
            return
        o = n * self.rec_size
        if _bit(img, self.USED, n):
            img[o:o + self.rec_size] = bytes(self.rec_size)
        _setbit(img, self.USED, n, False)
        r = img[o:o + self.rec_size]
        fv, fflag = self._encode_freq(m.freq)
        ov, oflag = self._encode_freq(m.offset)
        if fv > 0x3FFFF or ov > 0xFFFF:
            raise ValueError("Frequência/offset grande demais")
        keep = _u24(r, 0) & ~(0x3FFFF | 0x040000 | 0x200000) & 0xFFFFFF
        _put24(r, 0, keep | fv | (0x200000 if fflag else 0)
               | (0x040000 if oflag else 0))
        _put16(r, 3, ov)
        w = _u16(r, 5)
        _put16(r, 5, (m.rtone << 10) | (m.ctone << 4) | (w & 0x08) | m.mode)
        r[7] = m.dtcs
        r[8] = (m.step << 4) | (m.dsql << 2) | (r[8] & 0x03)
        r[10] = (m.tmode << 4) | (m.duplex << 2) | m.dtcs_pol
        r[11:27] = m.name.ljust(16)[:16].encode("ascii")
        r[27] = (r[27] & 0x80) | m.dv_code
        r[28:35] = encode_call(m.urcall)
        r[35:42] = encode_call(m.rpt1)
        r[42:49] = encode_call(m.rpt2)
        img[o:o + self.rec_size] = r
        # ID-51: "P" liga skip e pskip; "S" só skip
        _setbit(img, self.SKIP, n, m.skip in ("S", "P"))
        _setbit(img, self.PSKIP, n, m.skip == "P")
        b = self.BANKS + 2 * n
        img[b] = (img[b] & 0xE0) | (0x1F if m.bank is None else m.bank)
        img[b + 1] = m.bank_index


class ID880H(IcomModel):
    key = "id880h"
    name = "ID-880H"
    model_id = b"\x31\x67\x00\x01"
    memsize = 62976
    ranges = [(0x0000, 0xF5C0, 32), (0xF5C0, 0xF5E0, 16),
              (0xF5E0, 0xF600, 32)]
    endframe = b"Icom Inc.B1"
    num_memories = 1000
    rec_size = 41
    name_len = 8
    bank_name_len = 6
    bank_names_at = 0xB550
    USED, SKIP, PSKIP, BANKS = 0xAA80, 0xAB04, 0xAB88, 0xAD00
    MULT = [5000, 6250, 6250, 8333, 9000]
    modes = {0: "FM", 1: "NFM", 2: "WFM", 3: "AM", 4: "NAM", 5: "DV"}
    edit_modes = [0, 1, 3, 4, 5]
    steps = [5.0, 6.25, 8.33, 9.0, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0,
             50.0, 100.0, 125.0, 200.0]
    bands = [(118_000_000, 173_995_000), (230_000_000, 549_995_000),
             (810_000_000, 823_990_000), (849_000_000, 868_990_000),
             (894_000_000, 999_990_000)]
    tmode_labels = {0: "Off", 1: "Tone", 2: "TSQL", 3: "TSQL (cód. 3)",
                    4: "DTCS (cód. 4, beep)", 5: "DTCS", 6: "TSQL-R",
                    7: "DTCS-R"}
    default_tsql, default_dtcs = 2, 5
    icf_meta = {"Comment": "", "MapRev": 1, "EtcData": 0}
    icf_recordsize = 16

    def decode(self, img, n: int) -> IcomMemory:
        m = IcomMemory(number=n)
        if n < self.num_memories:
            if _bit(img, self.SKIP, n):
                m.skip = "S"
            elif _bit(img, self.PSKIP, n):
                m.skip = "P"
        if _bit(img, self.USED, n):
            m.skip = ""
            return m
        o = n * self.rec_size
        r = img[o:o + self.rec_size]
        f = _u24(r, 0)
        rxm, txm = (f >> 21) & 7, (f >> 18) & 7
        w = _u16(r, 5)
        m.empty = False
        m.freq = (f & 0x3FFFF) * self.MULT[min(rxm, 4)]
        m.offset = _u16(r, 3) * self.MULT[min(txm, 4)]
        m.rtone = min(w >> 10, len(TONES) - 1)
        m.ctone = min((w >> 4) & 0x3F, len(TONES) - 1)
        m.mode = w & 0x07
        m.dtcs = min(r[7], len(DTCS_CODES) - 1)
        m.step = r[8] >> 4
        if m.step >= len(self.steps):
            m.step = 0
        m.tmode = (r[10] >> 4) & 0x07
        m.duplex = (r[10] >> 2) & 0x03
        if m.duplex == 3:
            m.duplex = 0
        m.dtcs_pol = r[10] & 0x03
        m.name = _text(r[11:19])
        m.dv_code = r[19] & 0x7F
        m.urcall = decode_call(r[20:27])
        m.rpt1 = decode_call(r[27:34])
        m.rpt2 = decode_call(r[34:41])
        bank = img[self.BANKS + 2 * n]
        m.bank = None if bank == 0xFF or bank >= self.num_banks else bank
        m.bank_index = img[self.BANKS + 2 * n + 1]
        return m

    def _encode_freq(self, hz: int) -> tuple[int, int]:
        for i, step in enumerate(self.MULT):
            if hz % step == 0:
                return hz // step, i
        raise ValueError(f"{hz / 1e6:.6f} MHz não é múltiplo dos passos "
                         "suportados (5; 6,25; 8,33; 9 kHz)")

    def _mark_empty(self, img: bytearray, n: int) -> None:
        o = n * self.rec_size
        img[o:o + self.rec_size] = b"\xFF" * self.rec_size
        _setbit(img, self.USED, n, True)
        img[self.BANKS + 2 * n] = 0xFF

    def encode(self, img: bytearray, m: IcomMemory) -> None:
        self.validate(m)
        n = m.number
        _setbit(img, self.SKIP, n, m.skip == "S")
        _setbit(img, self.PSKIP, n, m.skip == "P")
        if m.empty:
            self._mark_empty(img, n)
            return
        o = n * self.rec_size
        if _bit(img, self.USED, n):
            img[o:o + self.rec_size] = bytes(self.rec_size)
        _setbit(img, self.USED, n, False)
        r = img[o:o + self.rec_size]
        fv, fm = self._encode_freq(m.freq)
        ov, om = self._encode_freq(m.offset)
        if fv > 0x3FFFF or ov > 0xFFFF:
            raise ValueError("Frequência/offset grande demais")
        _put24(r, 0, (fm << 21) | (om << 18) | fv)
        _put16(r, 3, ov)
        w = _u16(r, 5)
        _put16(r, 5, (m.rtone << 10) | (m.ctone << 4) | (w & 0x08) | m.mode)
        r[7] = m.dtcs
        r[8] = (m.step << 4) | (r[8] & 0x0F)
        r[10] = (r[10] & 0x80) | (m.tmode << 4) | (m.duplex << 2) | m.dtcs_pol
        r[11:19] = m.name.ljust(8)[:8].encode("ascii")
        r[19] = (r[19] & 0x80) | m.dv_code
        r[20:27] = encode_call(m.urcall)
        r[27:34] = encode_call(m.rpt1)
        r[34:41] = encode_call(m.rpt2)
        img[o:o + self.rec_size] = r
        img[self.BANKS + 2 * n] = 0xFF if m.bank is None else m.bank
        img[self.BANKS + 2 * n + 1] = m.bank_index


MODELS: dict[str, IcomModel] = {m.key: m for m in (ID51Plus2(), ID880H())}


def model_for_id(model_id: bytes) -> IcomModel | None:
    for m in MODELS.values():
        if m.model_id == model_id:
            return m
    return None
