"""Rádio Icom simulado em modo de clonagem (porta "SIMULADOR")."""

from __future__ import annotations

import struct
import threading

from . import clone as C
from .models import IcomMemory, IcomModel


class SimulatedIcom:
    def __init__(self, model: IcomModel, echo: bool = False):
        self.model = model
        self.echo = echo
        self.timeout = 0.02
        self.baudrate = 9600
        self._in = b""
        self._out = b""
        self._lock = threading.Lock()
        img = model.blank_image()
        demo = [
            IcomMemory(0, False, 145_500_000, name="CHAMADA"),
            IcomMemory(1, False, 146_940_000, 600_000, duplex=1,
                       tmode=1, rtone=12, step=8, name="RPT 2M", bank=0),
            IcomMemory(2, False, 439_975_000, 5_000_000, duplex=1, mode=5,
                       step=8, name="DSTAR UHF", urcall="CQCQCQ",
                       rpt1="PY2KXX B", rpt2="PY2KXX G", skip="S"),
        ]
        for m in demo:
            if len(m.name) > model.name_len:
                m.name = m.name[:model.name_len]
            model.encode(img, m)
        # o rádio guarda a imagem "nativa" (com o bit alto invertido no
        # ID-51 Plus2)
        self.native = C.flip_high_bit(img) if model.highbit_flip else img
        self.receiving = False

    # ---- interface serial mínima
    @property
    def in_waiting(self) -> int:
        return len(self._out)

    def write(self, data: bytes) -> int:
        with self._lock:
            self._in += data
            while True:
                s = self._in.find(b"\xFE\xFE")
                if s < 0:
                    self._in = b""
                    break
                e = self._in.find(b"\xFD", s)
                if e < 0:
                    self._in = self._in[s:]
                    break
                frame, self._in = self._in[s:e + 1], self._in[e + 1:]
                while frame.startswith(b"\xFE\xFE\xFE"):
                    frame = frame[1:]
                if self.echo:
                    self._out += frame
                self._handle(frame[4], frame[5:-1])
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

    # ---- protocolo
    def _send(self, cmd: int, payload: bytes) -> None:
        self._out += C.pack_frame(C.ADDR_RADIO, C.ADDR_PC, cmd, payload)

    def _handle(self, cmd: int, payload: bytes) -> None:
        m = self.model
        if cmd == C.CMD_ID:
            md = m.model_id + b"\x00\x01" + b"SIMULADOR".ljust(16) + \
                bytes(13) + b"31670101000001"
            self._send(C.CMD_MODEL, md)
        elif cmd == C.CMD_OUT:
            wide = m.memsize >= 0x10000
            for start, stop, bs in m.ranges:
                for addr in range(start, stop, bs):
                    size = min(bs, stop - addr)
                    chunk = struct.pack(">IB" if wide else ">HB", addr,
                                        size) + self.native[addr:addr + size]
                    self._send(C.CMD_DAT,
                               C.encode_payload(m, chunk, False, True))
            self._send(C.CMD_END, C.encode_payload(m, m.endframe, True,
                                                   False))
        elif cmd == C.CMD_IN:
            self.receiving = True
        elif cmd == C.CMD_DAT and self.receiving:
            addr, body = C.decode_data_payload(m, payload)
            self.native[addr:addr + len(body)] = body
        elif cmd == C.CMD_END and self.receiving:
            self.receiving = False
            self._send(C.CMD_OK, b"\x00")
