"""Protocolo de clonagem Icom (quadros FE FE ... FD).

Comandos: E0 identificação, E1 resposta de modelo, E2 clone do rádio para o
PC, E3 clone do PC para o rádio, E4 dados, E5 fim, E6 resultado,
E8 alta velocidade (38400 bps). Endereços: PC = EE, rádio = EF.

Quadros de dados: endereço (2 bytes, ou 4 se a memória tem >= 64 KiB),
tamanho (1), dados e checksum (complemento de dois da soma). Na maioria dos
rádios o conteúdo vai em hexadecimal ASCII; em alguns (ID-51 Plus2) vai em
binário, com bytes > F9 escapados como FF 0x.
"""

from __future__ import annotations

import struct
import threading
import time
from typing import Callable

from .models import IcomModel

CMD_ID, CMD_MODEL, CMD_OUT, CMD_IN = 0xE0, 0xE1, 0xE2, 0xE3
CMD_DAT, CMD_END, CMD_OK, CMD_HISPEED = 0xE4, 0xE5, 0xE6, 0xE8
ADDR_PC, ADDR_RADIO = 0xEE, 0xEF

ProgressFn = Callable[[int, int, str], None]
LogFn = Callable[[str, str], None]


class CloneError(Exception):
    pass


class CloneCancelled(CloneError):
    pass


def checksum(data: bytes) -> int:
    return (-sum(data)) & 0xFF


def escape_raw(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        out += bytes([0xFF, b & 0x0F]) if b > 0xF9 else bytes([b])
    return bytes(out)


def unescape_raw(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0xFF:
            i += 1
            if i >= len(data):
                raise CloneError("Escape incompleto no fim do quadro")
            b = 0xF0 | data[i]
        out.append(b)
        i += 1
    return bytes(out)


def flip_high_bit(data: bytes) -> bytearray:
    return bytearray(b ^ 0x80 for b in data)


def encode_payload(model: IcomModel, data: bytes, raw: bool,
                   add_checksum: bool) -> bytes:
    if add_checksum:
        data = data + bytes([checksum(data)])
    if model.raw_frames:
        return escape_raw(data)
    if raw:
        return data
    return data.hex().upper().encode("ascii")


def decode_data_payload(model: IcomModel, payload: bytes
                        ) -> tuple[int, bytes]:
    if model.raw_frames:
        data = unescape_raw(payload)
    else:
        try:
            data = bytes.fromhex(payload.decode("ascii"))
        except (ValueError, UnicodeDecodeError) as e:
            raise CloneError(f"Quadro de dados inválido: {e}") from e
    wide = model.memsize >= 0x10000
    hdr = 5 if wide else 3
    if len(data) < hdr + 1:
        raise CloneError("Quadro de dados curto demais")
    addr = struct.unpack(">I" if wide else ">H", data[:hdr - 1])[0]
    length = data[hdr - 1]
    body = data[hdr:hdr + length]
    if len(body) != length or len(data) < hdr + length + 1:
        raise CloneError(f"Quadro truncado no endereço {addr:05X}")
    if checksum(data[:hdr + length]) != data[hdr + length]:
        raise CloneError(f"Checksum incorreto no endereço {addr:05X}")
    return addr, body


def pack_frame(src: int, dst: int, cmd: int, payload: bytes) -> bytes:
    return bytes([0xFE, 0xFE, src, dst, cmd]) + payload + b"\xFD"


class FrameStream:
    """Lê quadros da serial, descartando o eco dos quadros enviados."""

    def __init__(self, ser, log: LogFn | None = None):
        self.ser = ser
        self.buf = b""
        self.echo: bool | None = None
        self.log = log or (lambda d, t: None)

    def send(self, cmd: int, payload: bytes, prefix: bytes = b"") -> None:
        frame = pack_frame(ADDR_PC, ADDR_RADIO, cmd, payload)
        if cmd != CMD_DAT:
            self.log("TX", frame.hex(" ").upper())
        self.ser.write(prefix + frame)

    def _parse(self) -> list[tuple[int, int, int, bytes]]:
        frames = []
        while True:
            start = self.buf.find(b"\xFE\xFE")
            if start < 0:
                self.buf = b""
                break
            self.buf = self.buf[start:]
            while self.buf.startswith(b"\xFE\xFE\xFE"):
                self.buf = self.buf[1:]
            end = self.buf.find(b"\xFD")
            if end < 0 or len(self.buf) < 5:
                break
            raw, self.buf = self.buf[:end + 1], self.buf[end + 1:]
            if len(raw) < 6:
                continue
            src, dst, cmd = raw[2], raw[3], raw[4]
            if src == ADDR_PC and dst == ADDR_RADIO:
                if self.echo is None:
                    self.log("INFO", "Cabo com eco detectado")
                self.echo = True
                frames.append(("echo", cmd, raw[5:-1]))
                continue
            if self.echo is None:
                self.echo = False
            frames.append(("radio", cmd, raw[5:-1]))
        return frames

    def read(self, timeout: float, want_echo: bool = False,
             max_frames: int | None = None) -> list[tuple[int, bytes]]:
        """Lê quadros do rádio até `timeout` sem dados (ou max_frames)."""
        out: list[tuple[int, bytes]] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self.ser.read(max(1, getattr(self.ser, "in_waiting", 0)))
            if chunk:
                self.buf += chunk
                deadline = time.monotonic() + timeout
                for kind, cmd, payload in self._parse():
                    if kind == "radio" or want_echo:
                        out.append((cmd, payload))
                if max_frames and len(out) >= max_frames:
                    break
        return out

    def munch_echo(self) -> None:
        """Consome o eco do último quadro (cabos que ecoam)."""
        if self.echo is False:
            return
        self.read(0.3 if self.echo is None else 1.0, want_echo=True,
                  max_frames=1)


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise CloneCancelled("Cancelado")


def identify(stream: FrameStream, model: IcomModel) -> bytes:
    stream.send(CMD_ID, encode_payload(model, b"\x00\x00\x00\x00", True,
                                       False))
    frames = stream.read(1.0, max_frames=1)
    if not frames:
        raise CloneError("O rádio não respondeu. Verifique o cabo e se o "
                         "rádio está em modo de clonagem.")
    md = frames[0][1]
    if md[:4] != model.model_id:
        raise CloneError(f"Rádio respondeu modelo {md[:4].hex(' ')}; "
                         f"esperado {model.name} "
                         f"({model.model_id.hex(' ')})")
    return md


def _start(stream: FrameStream, model: IcomModel, cmd: int,
           hispeed: bool) -> None:
    if hispeed and model.hispeed:
        stream.ser.write(b"\xFE" * 20 + pack_frame(
            ADDR_PC, ADDR_RADIO, CMD_HISPEED,
            model.model_id + b"\x00\x00\x02\x01\xFD"))
        time.sleep(0.25)
        stream.read(0.2)
        stream.ser.baudrate = 38400
        stream.log("INFO", "Alta velocidade: 38400 bps")
        stream.send(cmd, model.model_id[:3] + b"\x00", prefix=b"\xFE" * 14)
    else:
        stream.send(cmd, encode_payload(model, model.model_id, True, False))


def clone_from_radio(ser, model: IcomModel, progress: ProgressFn,
                     cancel: threading.Event | None = None,
                     hispeed: bool = True,
                     log: LogFn | None = None) -> bytearray:
    stream = FrameStream(ser, log)
    progress(0, model.memsize, "Identificando rádio...")
    identify(stream, model)
    _start(stream, model, CMD_OUT, hispeed)
    img = bytearray(model.memsize)
    received = 0
    last = time.monotonic()
    while True:
        _check(cancel)
        frames = stream.read(0.2)
        if not frames:
            if time.monotonic() - last > 10:
                raise CloneError("O fluxo de dados parou antes do fim da "
                                 f"clonagem ({received} bytes recebidos)")
            continue
        last = time.monotonic()
        for cmd, payload in frames:
            if cmd == CMD_DAT:
                addr, body = decode_data_payload(model, payload)
                if addr + len(body) > model.memsize:
                    raise CloneError(f"Endereço {addr:05X} fora da memória")
                img[addr:addr + len(body)] = body
                received = max(received, addr + len(body))
            elif cmd == CMD_END:
                if received < model.memsize:
                    raise CloneError(f"Clonagem incompleta: {received} de "
                                     f"{model.memsize} bytes")
                progress(model.memsize, model.memsize, "Clonagem concluída")
                return flip_high_bit(img) if model.highbit_flip else img
        progress(received, model.memsize,
                 f"Recebendo {received}/{model.memsize} bytes")


def clone_to_radio(ser, model: IcomModel, image: bytes,
                   progress: ProgressFn,
                   cancel: threading.Event | None = None,
                   hispeed: bool = True, log: LogFn | None = None,
                   map_rev: int = 1) -> None:
    if len(image) != model.memsize:
        raise CloneError("Tamanho da imagem não corresponde ao modelo")
    data = flip_high_bit(image) if model.highbit_flip else bytes(image)
    stream = FrameStream(ser, log)
    progress(0, model.memsize, "Identificando rádio...")
    md = identify(stream, model)
    if len(md) == 49 and md[5] != map_rev:
        raise CloneError(f"Revisão do rádio ({md[5]}) diferente da imagem "
                         f"({map_rev})")
    _start(stream, model, CMD_IN, hispeed)
    wide = model.memsize >= 0x10000
    for start, stop, bs in model.ranges:
        for addr in range(start, stop, bs):
            _check(cancel)
            size = min(bs, stop - addr)
            chunk = struct.pack(">IB" if wide else ">HB", addr, size) + \
                data[addr:addr + size]
            stream.send(CMD_DAT, encode_payload(model, chunk, False, True))
            stream.munch_echo()
            progress(addr + size, model.memsize,
                     f"Enviando {addr + size}/{model.memsize} bytes")
    stream.send(CMD_END, encode_payload(model, model.endframe, True, False))
    for _ in range(10):
        for cmd, payload in stream.read(0.5):
            if cmd == CMD_OK:
                if payload[:1] != b"\x00":
                    raise CloneError("O rádio rejeitou a clonagem")
                progress(model.memsize, model.memsize, "Clonagem concluída")
                return
    raise CloneError("O rádio não confirmou o fim da clonagem")
