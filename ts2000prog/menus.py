"""Definições dos menus do TS-2000 (comando EX).

Cada item: número no painel (ex. "06A"), índice EX (P1), sub-menu (P2),
descrição e opções {valor_cat: rótulo}.

`verified=True` indica itens cujo índice/valores foram confirmados em
software de terceiros (Hamlib, flrig). Os demais seguem a numeração do painel
do rádio e devem ser conferidos com o manual; o app permite editar qualquer
menu em formato bruto e "Varrer menus" descobre o que o rádio responde.

Para personalizar, use "Menus > Exportar definições", edite o JSON gerado e
salve-o como `menus_ts2000.json` ao lado do programa (ou na pasta do usuário
~/.ts2000prog/). Ele substitui a tabela abaixo.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

from .protocol import menu_key


@dataclass
class MenuDef:
    label: str                  # número exibido no painel ("12", "06A")
    ex: int                     # P1 do comando EX
    sub: int                    # P2 do comando EX
    name: str
    options: dict[str, str] = field(default_factory=dict)
    verified: bool = False

    @property
    def key(self) -> str:
        return menu_key(self.ex, self.sub)

    @property
    def width(self) -> int | None:
        return len(next(iter(self.options))) if self.options else None

    def display(self, raw: str | None) -> str:
        if raw is None:
            return ""
        return self.options.get(raw, raw)

    def to_dict(self) -> dict:
        return {"label": self.label, "ex": self.ex, "sub": self.sub,
                "name": self.name, "options": self.options,
                "verified": self.verified}


def _opts(*labels: str, width: int = 1) -> dict[str, str]:
    return {f"{i:0{width}d}": lab for i, lab in enumerate(labels)}


ONOFF = _opts("OFF", "ON")
LEVEL9 = _opts("OFF", *[str(i) for i in range(1, 10)])

_DEFAULTS: list[MenuDef] = [
    MenuDef("00", 0, 0, "Brilho do display", _opts("OFF", "1", "2", "3", "4")),
    MenuDef("01", 1, 0, "Iluminação das teclas", ONOFF),
    MenuDef("02", 2, 0, "Passos por volta do dial principal",
            _opts("500", "1000")),
    MenuDef("03", 3, 0, "Sintonia com o controle MULTI/CH", ONOFF),
    MenuDef("04", 4, 0, "Arredondar freq. VFO alterada pelo MULTI/CH", ONOFF),
    MenuDef("05", 5, 0, "Passo de 9 kHz no MULTI/CH (radiodifusão AM)", ONOFF),
    MenuDef("06A", 6, 0, "Operação split Memória-VFO", ONOFF),
    MenuDef("06B", 6, 1, "Frequência de memória variável temporária", ONOFF),
    MenuDef("07", 7, 0, "Varredura de programa parcialmente lenta", ONOFF),
    MenuDef("08", 8, 0, "Faixa de redução de velocidade",
            _opts("100 Hz", "200 Hz", "300 Hz", "400 Hz", "500 Hz")),
    MenuDef("09", 9, 0, "Retenção da varredura de programa", ONOFF),
    MenuDef("10", 10, 0, "Método de retomada da varredura",
            _opts("TO (tempo)", "CO (portadora)")),
    MenuDef("11", 11, 0, "Faixa da varredura visual",
            _opts("31 ch", "61 ch", "91 ch", "181 ch")),
    MenuDef("12", 12, 0, "Volume do beep", LEVEL9, verified=True),
    MenuDef("13", 13, 0, "Volume do sidetone (TX CW)", LEVEL9, verified=True),
    MenuDef("14", 14, 0, "Volume de reprodução de mensagens", LEVEL9),
    MenuDef("15", 15, 0, "Volume do anúncio de voz", LEVEL9),
    MenuDef("16", 16, 0, "Configuração da saída de áudio (MAIN/SUB)", {}),
    MenuDef("17", 17, 0, "Saída de áudio invertida", ONOFF),
    MenuDef("18", 18, 0, "Manter TX quando o AT concluir a sintonia", ONOFF),
    MenuDef("19", 19, 0, "AT em linha durante a recepção", ONOFF),
    MenuDef("20", 20, 0, "Equalizador DSP de RX",
            _opts("OFF", "High boost", "Formant pass", "Bass boost",
                  "Conventional", "User"), verified=True),
    MenuDef("21", 21, 0, "Equalizador DSP de TX",
            _opts("OFF", "High boost", "Formant pass", "Bass boost",
                  "Conventional", "User"), verified=True),
    MenuDef("22", 22, 0, "Largura do filtro DSP de TX (SSB/AM)",
            _opts("2.0 kHz", "2.2 kHz", "2.4 kHz", "2.6 kHz", "2.8 kHz",
                  "3.0 kHz"), verified=True),
    MenuDef("23", 23, 0, "Ajuste fino da potência de TX", ONOFF),
    MenuDef("24", 24, 0, "Temporizador de TX (time-out)",
            _opts("OFF", "3 min", "5 min", "10 min", "20 min", "30 min")),
    MenuDef("25", 25, 0, "Exibição de frequência do transverter", ONOFF),
    MenuDef("26", 26, 0, "Redução de potência com transverter", ONOFF),
    MenuDef("27", 27, 0, "Inibir TX", ONOFF),
    MenuDef("28", 28, 0, "Menu 28", {}),
    MenuDef("29", 29, 0, "Menu 29", {}),
    MenuDef("30", 30, 0, "Menu 30", {}),
    MenuDef("31", 31, 0, "Pitch de CW / deslocamento de BFO",
            {f"{i:02d}": f"{400 + 50 * i} Hz" for i in range(13)},
            verified=True),
    MenuDef("32", 32, 0, "Tempo de subida do CW",
            _opts("1 ms", "2 ms", "4 ms", "6 ms")),
    MenuDef("33", 33, 0, "Ponderação do keyer de CW", {}),
    MenuDef("34", 34, 0, "Ponderação automática reversa do keyer", ONOFF),
    MenuDef("35", 35, 0, "Função bug key", ONOFF),
    MenuDef("36", 36, 0, "TX CW automático no modo SSB", ONOFF),
    MenuDef("37", 37, 0, "Correção de frequência SSB → CW", ONOFF),
    MenuDef("38", 38, 0, "Menu 38", {}),
    MenuDef("39", 39, 0, "Shift de FSK",
            _opts("170 Hz", "200 Hz", "425 Hz", "850 Hz")),
    MenuDef("40", 40, 0, "Polaridade de chaveamento FSK", ONOFF),
    MenuDef("41", 41, 0, "Frequência do tom FSK", _opts("1275 Hz", "2125 Hz")),
] + [
    MenuDef(f"{n:02d}", n, 0, f"Menu {n:02d}", {}) for n in range(42, 56)
] + [
    MenuDef("56", 56, 0, "Velocidade da porta COM",
            _opts("4800", "9600", "19200", "38400", "57600")),
] + [
    MenuDef(f"{n:02d}", n, 0, f"Menu {n:02d}", {}) for n in range(57, 63)
]


def _search_paths() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(os.getcwd(), "menus_ts2000.json"),
        os.path.join(os.path.dirname(here), "menus_ts2000.json"),
        os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                     "menus_ts2000.json"),
        os.path.join(os.path.expanduser("~"), ".ts2000prog",
                     "menus_ts2000.json"),
    ]


def load_menu_defs(path: str | None = None) -> tuple[list[MenuDef], str]:
    """Carrega definições; retorna (lista, origem)."""
    candidates = [path] if path else _search_paths()
    for p in candidates:
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            defs = [MenuDef(label=d["label"], ex=int(d["ex"]),
                            sub=int(d.get("sub", 0)), name=d["name"],
                            options={str(k): str(v) for k, v in
                                     d.get("options", {}).items()},
                            verified=bool(d.get("verified", False)))
                    for d in data["menus"]]
            return defs, p
    return [MenuDef(**{**d.to_dict(), "options": dict(d.options)})
            for d in _DEFAULTS], "interna"


def save_menu_defs(defs: list[MenuDef], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"menus": [d.to_dict() for d in defs]}, fh,
                  ensure_ascii=False, indent=2)
