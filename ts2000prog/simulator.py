"""Rádio TS-2000 simulado, com a mesma interface mínima de serial.Serial.

Permite testar o programa sem o rádio (porta "SIMULADOR").
"""

from __future__ import annotations

import random
import threading
import time

from . import protocol as P
from .menus import load_menu_defs


class SimulatedRadio:
    def __init__(self):
        self.timeout = 0.05
        self._in = b""
        self._out = b""
        self._lock = threading.Lock()
        self.ai = "0"
        self.mem: dict[tuple[int, int], str] = {}     # (p1, canal) -> corpo
        self.menus: dict[str, str] = {}
        self.reject_menus: set[str] = set()
        defs, _ = load_menu_defs()
        for d in defs:
            self.menus[d.key] = next(iter(d.options), "0") \
                if d.options else "0"
        self._seed()
        # estado "ao vivo" para o display
        self.freq_a = 14_195_000
        self.freq_b = 145_500_000
        self.mode = 2
        self.s = 8
        self.t0 = time.monotonic()

    def _seed(self) -> None:
        demo = [
            P.Memory(0, False, 145_500_000, 4, name="CHAMADA"),
            P.Memory(1, False, 146_940_000, 4, tone_mode=1, tone=12,
                     shift=2, offset=600_000, step=6, name="RPT 2M"),
            P.Memory(2, False, 7_050_000, 1, step=0, name="40M LSB"),
            P.Memory(3, False, 439_975_000, 4, tone_mode=3, dcs=10, shift=2,
                     offset=5_000_000, step=6, group=1, name="UHF DCS"),
            P.Memory(4, False, 14_195_000, 2, tx_freq=14_225_000, name="DX SPL"),
            P.Memory(290, False, 144_000_000, 4, tx_freq=148_000_000, step=6),
        ]
        for m in demo:
            for cmd in P.cmds_write_memory(m):
                self._handle(cmd[:-1])
        self._out = b""

    # ---------------------------------------------------- interface serial
    @property
    def in_waiting(self) -> int:
        return len(self._out)

    def write(self, data: bytes) -> int:
        with self._lock:
            self._in += data
            while b";" in self._in:
                cmd, self._in = self._in.split(b";", 1)
                self._handle(cmd.decode("ascii"))
        return len(data)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            chunk, self._out = self._out[:n], self._out[n:]
        if not chunk:
            threading.Event().wait(self.timeout)
        return chunk

    def reset_input_buffer(self) -> None:
        self._out = b""

    def close(self) -> None:
        pass

    # ------------------------------------------------------- estado ao vivo
    def _phase(self) -> str:
        """Ciclo de 20 s: sintonizando, ouvindo, transmitindo."""
        t = (time.monotonic() - self.t0) % 20
        return "tune" if t < 3 else ("tx" if 14 < t < 18 else "rx")

    def _if_reply(self) -> str:
        phase = self._phase()
        if phase == "tune":
            self.freq_a += 50
        tx = "1" if phase == "tx" else "0"
        return (f"IF{self.freq_a:011d}00000+0120" "1" "0" "005"
                f"{tx}{self.mode}0" "0" "0" "0" "08" "0")

    # ------------------------------------------------------- interpretador
    def _reply(self, s: str) -> None:
        self._out += (s + ";").encode("ascii")

    def _handle(self, cmd: str) -> None:
        if not cmd:
            return
        c = cmd[:2]
        if cmd == "ID":
            self._reply("ID019")
        elif c == "AI":
            if len(cmd) == 2:
                self._reply("AI" + self.ai)
            else:
                self.ai = cmd[2]
        elif c == "MR" and len(cmd) == 6:
            p1, num = int(cmd[2]), int(cmd[3:6])
            if num >= P.NUM_MEMORIES:
                self._reply("?")
                return
            body = self.mem.get((p1, num), "0" * 35)
            self._reply(f"MR{p1}{num:03d}{body}")
        elif c == "MW" and len(cmd) >= 41:
            p1, num, body = int(cmd[2]), int(cmd[3:6]), cmd[6:]
            if num >= P.NUM_MEMORIES or len(body) > 43:
                self._reply("?")
                return
            if p1 == 0:
                self.mem[(0, num)] = body
                self.mem[(1, num)] = body   # rádio copia RX para TX
            else:
                self.mem[(1, num)] = body
        elif cmd == "IF":
            self._reply(self._if_reply())
        elif cmd == "SM0":
            t = self._phase()
            if t == "tx":
                self.s = random.randint(18, 26)
            else:
                self.s = max(0, min(30, self.s + random.randint(-3, 3)))
            self._reply(f"SM0{self.s:04d}")
        elif c in ("FA", "FB"):
            if len(cmd) == 2:
                f = self.freq_a if c == "FA" else self.freq_b
                self._reply(f"{c}{f:011d}")
            elif c == "FA":
                self.freq_a = int(cmd[2:])
            else:
                self.freq_b = int(cmd[2:])
        elif cmd == "PC":
            self._reply("PC100")
        elif cmd == "PA":
            self._reply("PA10")
        elif cmd == "RA":
            self._reply("RA00")
        elif cmd == "NB":
            self._reply("NB0")
        elif cmd == "NR":
            self._reply("NR1")
        elif c == "EX" and len(cmd) >= 9:
            key = cmd[2:7]
            if key not in self.menus or key in self.reject_menus:
                self._reply("?")
            elif len(cmd) == 9:
                self._reply(f"EX{key}00{self.menus[key]}")
            else:
                self.menus[key] = cmd[9:]
        else:
            self._reply("?")
