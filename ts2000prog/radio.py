"""Comunicação serial (CAT) com o TS-2000."""

from __future__ import annotations

import threading
import time
from typing import Callable, Iterable

from . import protocol as P
from .menus import MenuDef

LogFn = Callable[[str, str], None]          # (direção, texto)
ProgressFn = Callable[[int, int, str], None]  # (feito, total, mensagem)

BAUD_RATES = [4800, 9600, 19200, 38400, 57600]
SIMULATOR_PORT = "SIMULADOR"
EXPECTED_ID = "ID019"           # TS-2000/TS-B2000/TS-2000X


class RadioError(Exception):
    pass


class Cancelled(Exception):
    pass


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as lp
        ports = [p.device for p in lp.comports()]
    except Exception:
        ports = []
    return sorted(ports) + [SIMULATOR_PORT]


class CatLink:
    """Envia comandos terminados em ';' e lê respostas."""

    def __init__(self, ser, log: LogFn | None = None, timeout: float = 1.0):
        self.ser = ser
        self.log = log or (lambda d, t: None)
        self.timeout = timeout
        self._buf = b""
        self.lock = threading.RLock()

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def _write(self, cmd: str) -> None:
        self.log("TX", cmd)
        self.ser.write(cmd.encode("ascii"))

    def _read_reply(self, timeout: float | None = None) -> str | None:
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            idx = self._buf.find(b";")
            if idx >= 0:
                reply = self._buf[:idx + 1].decode("ascii", "replace")
                self._buf = self._buf[idx + 1:]
                self.log("RX", reply)
                return reply
            if time.monotonic() > deadline:
                if self._buf:
                    self.log("RX", self._buf.decode("ascii", "replace")
                             + "  (incompleto)")
                    self._buf = b""
                return None
            chunk = self.ser.read(max(1, getattr(self.ser, "in_waiting", 0)))
            if chunk:
                self._buf += chunk

    def flush(self) -> None:
        self._buf = b""
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def query(self, cmd: str, prefix: str, retries: int = 3) -> str:
        """Envia `cmd` e devolve a primeira resposta iniciada por `prefix`."""
        with self.lock:
            last = None
            for attempt in range(retries):
                self._write(cmd)
                deadline = time.monotonic() + 3 * self.timeout
                while True:
                    reply = self._read_reply()
                    if reply is None or time.monotonic() > deadline:
                        last = "sem resposta"
                        break
                    if reply.startswith(prefix):
                        return reply
                    if reply in ("?;", "E;", "O;"):
                        last = f"rádio respondeu {reply}"
                        time.sleep(0.05 * (attempt + 1))
                        break
                    # mensagem não solicitada (AI) — ignora
            raise RadioError(f"{cmd} -> {last}")

    def set(self, cmd: str, retries: int = 3) -> None:
        """Envia comando de escrita e confirma ausência de erro via ID;."""
        with self.lock:
            last = None
            for attempt in range(retries):
                self._write(cmd)
                self._write("ID;")
                error = None
                while True:
                    reply = self._read_reply()
                    if reply is None:
                        error = "sem resposta"
                        break
                    if reply in ("?;", "E;", "O;"):
                        error = f"rádio respondeu {reply}"
                        continue
                    if reply.startswith("ID"):
                        break
                if error is None:
                    return
                last = error
                time.sleep(0.05 * (attempt + 1))
            raise RadioError(f"{cmd} -> {last}")


class TS2000:
    def __init__(self, log: LogFn | None = None):
        self.log = log
        self.link: CatLink | None = None
        self._saved_ai: str | None = None
        self.radio_id = ""

    @property
    def connected(self) -> bool:
        return self.link is not None

    # ------------------------------------------------------------ conexão
    def connect(self, port: str, baud: int = 9600, rtscts: bool = True,
                stopbits: int = 1) -> str:
        if port == SIMULATOR_PORT:
            from .simulator import SimulatedRadio
            ser = SimulatedRadio()
        else:
            import serial
            ser = serial.Serial(
                port=port, baudrate=baud, bytesize=8, parity="N",
                stopbits=stopbits, timeout=0.05, rtscts=rtscts)
            if not rtscts:
                ser.rts = True
                ser.dtr = True
        link = CatLink(ser, self.log)
        try:
            link.flush()
            link._write(";")            # descarta comando parcial no rádio
            time.sleep(0.1)
            link.flush()
            rid = link.query("ID;", "ID").rstrip(";")
            if rid != EXPECTED_ID:
                raise RadioError(
                    f"Rádio respondeu {rid}; esperado {EXPECTED_ID} (TS-2000)")
            self._saved_ai = link.query("AI;", "AI").rstrip(";")[2:]
            if self._saved_ai != "0":
                link.set("AI0;")
        except Exception:
            link.close()
            raise
        self.link = link
        self.radio_id = rid
        return rid

    def disconnect(self) -> None:
        if not self.link:
            return
        try:
            if self._saved_ai and self._saved_ai != "0":
                self.link.set(f"AI{self._saved_ai};")
        except Exception:
            pass
        self.link.close()
        self.link = None

    def _require(self) -> CatLink:
        if not self.link:
            raise RadioError("Rádio não conectado")
        return self.link

    # ----------------------------------------------------------- memórias
    def read_memory(self, number: int) -> P.Memory:
        link = self._require()
        rx = link.query(P.cmd_read_memory(number), f"MR0{number:03d}")
        _, _, fields = P.parse_memory_reply(rx)
        tx = None
        if fields is not None:
            tx = link.query(P.cmd_read_memory(number, tx=True),
                            f"MR1{number:03d}")
        return P.memory_from_replies(number, rx, tx)

    def write_memory(self, mem: P.Memory) -> None:
        link = self._require()
        for cmd in P.cmds_write_memory(mem):
            link.set(cmd)

    # -------------------------------------------------------------- menus
    def read_menu(self, ex: int, sub: int = 0) -> str:
        link = self._require()
        reply = link.query(P.cmd_read_menu(ex, sub), f"EX{ex:03d}{sub:02d}")
        _, _, value = P.parse_menu_reply(reply)
        return value

    def write_menu(self, ex: int, sub: int, value: str) -> None:
        self._require().set(P.cmd_write_menu(ex, sub, value))

    # ----------------------------------------------------- operações em lote
    @staticmethod
    def _check(cancel: threading.Event | None) -> None:
        if cancel is not None and cancel.is_set():
            raise Cancelled()

    def download_memories(self, numbers: Iterable[int], progress: ProgressFn,
                          cancel: threading.Event | None = None
                          ) -> dict[int, P.Memory]:
        numbers = list(numbers)
        out: dict[int, P.Memory] = {}
        for i, n in enumerate(numbers):
            self._check(cancel)
            progress(i, len(numbers), f"Lendo canal {n:03d}")
            out[n] = self.read_memory(n)
        progress(len(numbers), len(numbers), "Memórias lidas")
        return out

    def upload_memories(self, mems: list[P.Memory], progress: ProgressFn,
                        cancel: threading.Event | None = None,
                        verify: bool = False) -> list[str]:
        errors: list[str] = []
        for i, m in enumerate(mems):
            self._check(cancel)
            progress(i, len(mems), f"Gravando canal {m.number:03d}")
            try:
                self.write_memory(m)
                if verify:
                    back = self.read_memory(m.number)
                    if not _same_memory(m, back):
                        errors.append(f"Canal {m.number:03d}: verificação "
                                      "diverge do que foi gravado")
            except (RadioError, ValueError) as e:
                errors.append(f"Canal {m.number:03d}: {e}")
        progress(len(mems), len(mems), "Memórias gravadas")
        return errors

    def download_menus(self, defs: list[MenuDef], progress: ProgressFn,
                       cancel: threading.Event | None = None
                       ) -> tuple[dict[str, str], list[str]]:
        values: dict[str, str] = {}
        errors: list[str] = []
        for i, d in enumerate(defs):
            self._check(cancel)
            progress(i, len(defs), f"Lendo menu {d.label}")
            try:
                values[d.key] = self.read_menu(d.ex, d.sub)
            except RadioError as e:
                errors.append(f"Menu {d.label}: {e}")
        progress(len(defs), len(defs), "Menus lidos")
        return values, errors

    def upload_menus(self, items: list[tuple[MenuDef, str]],
                     progress: ProgressFn,
                     cancel: threading.Event | None = None) -> list[str]:
        errors: list[str] = []
        for i, (d, value) in enumerate(items):
            self._check(cancel)
            progress(i, len(items), f"Gravando menu {d.label}")
            try:
                self.write_menu(d.ex, d.sub, value)
            except (RadioError, ValueError) as e:
                errors.append(f"Menu {d.label}: {e}")
        progress(len(items), len(items), "Menus gravados")
        return errors

    def scan_menus(self, ex_range: range, subs: range, progress: ProgressFn,
                   cancel: threading.Event | None = None) -> dict[str, str]:
        """Descobre quais combinações EX/sub o rádio aceita."""
        found: dict[str, str] = {}
        link = self._require()
        total = len(ex_range) * len(subs)
        done = 0
        old_timeout = link.timeout
        link.timeout = 0.4
        try:
            for ex in ex_range:
                for sub in subs:
                    self._check(cancel)
                    progress(done, total, f"Varrendo EX{ex:03d} sub {sub:02d}")
                    done += 1
                    try:
                        reply = link.query(P.cmd_read_menu(ex, sub),
                                           f"EX{ex:03d}{sub:02d}", retries=1)
                        found[P.menu_key(ex, sub)] = \
                            P.parse_menu_reply(reply)[2]
                    except RadioError:
                        if sub == subs.start:
                            done += len(subs) - 1
                            break       # menu inexistente: pula os subs
        finally:
            link.timeout = old_timeout
        progress(total, total, f"{len(found)} menus encontrados")
        return found


def _same_memory(a: P.Memory, b: P.Memory) -> bool:
    if a.empty or b.empty:
        return a.empty == b.empty
    keys = ["freq", "mode", "lockout", "tone_mode", "reverse", "shift",
            "offset", "step", "group"]
    if any(getattr(a, k) != getattr(b, k) for k in keys):
        return False
    if a.name.rstrip() != b.name.rstrip():
        return False
    if a.tone_mode and (a.tone, a.ctcss, a.dcs) != (b.tone, b.ctcss, b.dcs):
        return False
    return a.split == b.split and (not a.split or a.tx_freq == b.tx_freq)
