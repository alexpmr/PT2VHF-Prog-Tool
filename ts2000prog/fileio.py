"""Arquivos de projeto (.ts2k, JSON) e importação/exportação CSV."""

from __future__ import annotations

import csv
import json

from . import protocol as P

FORMAT = "ts2000prog"
VERSION = 1


class Codeplug:
    """Conteúdo completo editável do rádio."""

    def __init__(self):
        self.memories: dict[int, P.Memory] = {
            n: P.Memory(number=n) for n in range(P.NUM_MEMORIES)}
        self.menus: dict[str, str] = {}      # chave "EEESS" -> valor bruto

    def to_dict(self) -> dict:
        return {
            "format": FORMAT, "version": VERSION, "radio": "TS-2000",
            "memories": [m.to_dict() for m in self.memories.values()
                         if not m.empty],
            "menus": dict(sorted(self.menus.items())),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Codeplug":
        if d.get("format") != FORMAT:
            raise ValueError("Arquivo não é um projeto TS-2000")
        cp = cls()
        for md in d.get("memories", []):
            m = P.Memory.from_dict(md)
            cp.memories[m.number] = m
        cp.menus = {str(k): str(v) for k, v in d.get("menus", {}).items()}
        return cp


def save_project(cp: Codeplug, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cp.to_dict(), fh, ensure_ascii=False, indent=1)


def load_project(path: str) -> Codeplug:
    with open(path, encoding="utf-8") as fh:
        return Codeplug.from_dict(json.load(fh))


# ---------------------------------------------------------------------- CSV

CSV_COLUMNS = ["Canal", "RX MHz", "Modo", "TX MHz", "Modo TX", "Shift",
               "Offset MHz", "Tom tipo", "Tom Hz", "CTCSS Hz", "DCS",
               "Reverse", "Passo kHz", "Grupo", "Lockout", "Nome"]


def _mhz(hz: int) -> str:
    return f"{hz / 1e6:.6f}"


def _hz(text: str) -> int:
    text = text.strip().replace(",", ".")
    return round(float(text) * 1e6) if text else 0


def memory_to_row(m: P.Memory) -> list[str]:
    steps = P.steps_for_mode(m.mode)
    return [
        f"{m.number:03d}", _mhz(m.freq), P.MODES[m.mode],
        _mhz(m.tx_freq) if m.tx_freq and (m.split or P.is_program_scan(
            m.number)) else "",
        P.MODES.get(m.tx_mode, ""), P.SHIFTS[m.shift], _mhz(m.offset),
        P.TONE_MODES[m.tone_mode], f"{P.TONES[m.tone - 1]:.1f}",
        f"{P.TONES[m.ctcss - 1]:.1f}", f"{P.DCS_CODES[m.dcs]:03d}",
        "1" if m.reverse else "0", f"{steps[m.step]:g}", str(m.group),
        "1" if m.lockout else "0", m.name,
    ]


def row_to_memory(row: dict[str, str]) -> P.Memory:
    def get(col: str, default: str = "") -> str:
        return (row.get(col) or default).strip()

    def lookup(table: dict, text: str, what: str) -> int:
        for k, v in table.items():
            if v.lower() == text.lower():
                return k
        raise ValueError(f"{what} inválido: {text!r}")

    n = int(get("Canal"))
    mode = lookup(P.MODES, get("Modo", "FM"), "Modo")
    steps = P.steps_for_mode(mode)
    step_txt = get("Passo kHz")
    step = steps.index(float(step_txt)) if step_txt else 0
    tx_mode_txt = get("Modo TX")
    m = P.Memory(
        number=n, empty=False, freq=_hz(get("RX MHz")), mode=mode,
        tx_freq=_hz(get("TX MHz")),
        tx_mode=lookup(P.MODES, tx_mode_txt, "Modo TX") if tx_mode_txt else 0,
        shift=lookup(P.SHIFTS, get("Shift", "Simplex"), "Shift"),
        offset=_hz(get("Offset MHz", "0")),
        tone_mode=lookup(P.TONE_MODES, get("Tom tipo", "Off"), "Tom tipo"),
        tone=P.TONES.index(float(get("Tom Hz", "88.5"))) + 1,
        ctcss=P.TONES.index(float(get("CTCSS Hz", "88.5"))) + 1,
        dcs=P.DCS_CODES.index(int(get("DCS", "023"))),
        reverse=get("Reverse") == "1", step=step,
        group=int(get("Grupo", "0")), lockout=get("Lockout") == "1",
        name=get("Nome")[:P.NAME_LEN],
    )
    m.validate()
    return m


def export_csv(cp: Codeplug, path: str) -> int:
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_COLUMNS)
        for m in cp.memories.values():
            if not m.empty:
                w.writerow(memory_to_row(m))
                count += 1
    return count


def import_csv(path: str) -> tuple[list[P.Memory], list[str]]:
    mems, errors = [], []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            try:
                mems.append(row_to_memory(row))
            except (ValueError, KeyError, TypeError) as e:
                errors.append(f"Linha {i}: {e}")
    return mems, errors
