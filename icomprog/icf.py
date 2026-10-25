"""Arquivos .icf (formato dos softwares CS-51PLUS2 / CS-80/880 da Icom).

Linha 1: código do modelo em hexadecimal; linhas "#Chave=valor" de
metadados; linhas de dados "AAAALL<dados>" (endereço de 2 bytes) ou
"AAAAAAAALL<dados>" (endereço de 4 bytes, registros de 32 bytes). Arquivos
com registros de 32 bytes terminam com "#CD=<md5>".
"""

from __future__ import annotations

import binascii
import hashlib


def read_icf(path: str) -> tuple[bytes, dict, bytearray]:
    with open(path, encoding="ascii", errors="replace") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    if not lines:
        raise ValueError("Arquivo vazio")
    try:
        model = bytes.fromhex(lines[0][:8])
    except ValueError:
        raise ValueError("Não é um arquivo ICF") from None
    meta: dict = {}
    img = bytearray()
    for line in lines[1:]:
        if line.startswith("#"):
            if "=" in line:
                key, value = line[1:].split("=", 1)
                if key == "EtcData":
                    meta[key] = int(value, 16)
                elif value.isdigit():
                    meta[key] = int(value)
                else:
                    meta[key] = value
            continue
        if len(line) % 8 == 6:
            addr, size, data = int(line[:4], 16), int(line[4:6], 16), line[6:]
        else:
            addr, size, data = int(line[:8], 16), int(line[8:10], 16), \
                line[10:]
        chunk = bytes.fromhex(data[:size * 2])
        if addr != len(img):
            if addr > len(img):
                img.extend(bytes(addr - len(img)))
            else:
                raise ValueError(f"Endereço fora de ordem: {addr:X}")
        img += chunk
        meta.setdefault("recordsize", size)
    return model, meta, img


def _model_hash_prefix(model: bytes) -> bytes:
    a, b = model[0] >> 4, model[0] & 0x0F
    c, d = model[1] >> 4, model[1] & 0x0F
    return bytes([(a << 4) | a, (b << 4) | b, (c << 4) | c, (d << 4) | d,
                  (a << 4) | b, (c << 4) | d])


def write_icf(path: str, model: bytes, meta: dict, img: bytes,
              recordsize: int) -> None:
    lines = [model.hex(),
             f"#Comment={meta.get('Comment', '')}",
             f"#MapRev={meta.get('MapRev', 1)}",
             f"#EtcData={meta.get('EtcData', 0):06x}"]
    digest = _model_hash_prefix(model)
    for addr in range(0, len(img), recordsize):
        block = img[addr:addr + recordsize]
        if recordsize == 32:
            line = f"{addr:08X}{len(block):02X}{block.hex().upper()}"
            digest += binascii.unhexlify(line)
        else:
            line = f"{addr:04X}{len(block):02X}{block.hex().upper()}"
        lines.append(line)
    if recordsize == 32:
        lines.append(f"#CD={hashlib.md5(digest).hexdigest().upper()}")
    with open(path, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
