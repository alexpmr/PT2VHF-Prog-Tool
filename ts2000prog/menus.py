"""Definições dos menus do TS-2000 (comando EX).

Cada item: número no painel (ex. "06A"), índice EX (P1), sub-menu (P2),
descrição e opções {valor_cat: rótulo}.

A tabela segue o manual do TS-2000 (lista de menus e tabela de parâmetros
do comando EX). Qualquer menu também pode ser editado em formato bruto, e
"Varrer menus" mostra o que o rádio responde.

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
EQ = _opts("OFF", "H BOOST", "F PASS", "B BOOST", "CONVEN", "USER")
DELAY = _opts("OFF", "1", "2")
PF_CODES = {f"{n:02d}": f"Menu {n:02d}" for n in range(63)}
PF_CODES.update({
    "63": "VOICE1", "64": "VOICE2", "65": "RX MONI", "66": "DSP MONI",
    "67": "QUICK MEMO MR", "68": "QUICK MEMO M.IN", "69": "SPLIT",
    "70": "TF-SET", "71": "A/B", "72": "VFO/M", "73": "A=B", "74": "SCAN",
    "75": "M>VFO", "76": "M.IN", "77": "CW TUNE", "78": "CH1", "79": "CH2",
    "80": "CH3", "81": "FINE", "82": "CLR", "83": "CALL", "84": "CTRL",
    "85": "1MHz", "86": "ANT1/2", "87": "NB", "88": "N.R.", "89": "B.C.",
    "90": "A.N.", "99": "Sem função"})


def _m(label: str, name: str, options: dict[str, str] | None = None
       ) -> MenuDef:
    """Menu pelo número do painel: "12" -> EX012 00; "06A" -> EX006 01."""
    num, sub = int(label[:2]), 0
    if len(label) > 2:
        sub = ord(label[2]) - ord("A") + 1
    return MenuDef(label, num, sub, name, options or {}, verified=True)


# Tabela do manual do TS-2000 (MENU CONFIGURATION e "EX command parameter
# P5", págs. 22-26 e 119-122). Nos sub-menus (letras), P2 = 01 para A,
# 02 para B... ("00" quando o menu não tem sub-menu).
_DEFAULTS: list[MenuDef] = [
    _m("00", "Brilho do display", _opts("OFF", "1", "2", "3", "4")),
    _m("01", "Iluminação das teclas", ONOFF),
    _m("02", "Passos por volta do dial principal", _opts("500", "1000")),
    _m("03", "Sintonia com o controle MULTI/CH", ONOFF),
    _m("04", "Arredondar freq. VFO alterada pelo MULTI/CH", ONOFF),
    _m("05", "Passo de 9 kHz no MULTI/CH (radiodifusão AM)", ONOFF),
    _m("06A", "Operação split Memória-VFO", ONOFF),
    _m("06B", "Frequência de memória ajustável (ON) ou fixa (OFF)", ONOFF),
    _m("07", "Varredura de programa parcialmente lenta", ONOFF),
    _m("08", "Faixa de redução de velocidade da varredura",
       _opts("100 Hz", "200 Hz", "300 Hz", "400 Hz", "500 Hz")),
    _m("09", "Retenção da varredura de programa", ONOFF),
    _m("10", "Método de retomada da varredura",
       _opts("TO (tempo)", "CO (portadora)")),
    _m("11", "Faixa da varredura visual",
       _opts("31 ch", "61 ch", "91 ch", "181 ch")),
    _m("12", "Volume do beep", LEVEL9),
    _m("13", "Volume do sidetone de TX", LEVEL9),
    _m("14", "Volume de reprodução do DRU-3A", LEVEL9),
    _m("15", "Volume de reprodução do VS-3", LEVEL9),
    _m("16", "Saída de áudio EXT.SP2/fone",
       _opts("0: L/R = Main+Sub", "1: L = Main, R = Sub",
             "2: L = Main+¼Sub, R = Sub+¼Main")),
    _m("17", "Inverter saídas EXT.SP1/EXT.SP2 (L/R do fone)", ONOFF),
    _m("18", "Entrada pelo conector HF RX ANT", ONOFF),
    _m("19A", "Squelch pelo S-meter", ONOFF),
    _m("19B", "Tempo de retenção do squelch pelo S-meter",
       _opts("OFF", "125 ms", "250 ms", "500 ms")),
    _m("20", "Equalizador DSP de RX", EQ),
    _m("21", "Equalizador DSP de TX", EQ),
    _m("22", "Largura do filtro DSP de TX (SSB/AM)",
       _opts("2.0 kHz", "2.2 kHz", "2.4 kHz", "2.6 kHz", "2.8 kHz",
             "3.0 kHz")),
    _m("23", "Ajuste fino da potência de TX", ONOFF),
    _m("24", "Temporizador de TX (time-out)",
       _opts("OFF", "3 min", "5 min", "10 min", "20 min", "30 min")),
    _m("25", "Exibição de frequência do transverter", ONOFF),
    _m("26", "Manter TX quando o AT concluir a sintonia", ONOFF),
    _m("27", "AT em linha durante a recepção", ONOFF),
    _m("28A", "Atraso do controle do linear — HF", DELAY),
    _m("28B", "Atraso do controle do linear — 50 MHz", DELAY),
    _m("28C", "Atraso do controle do linear — 144 MHz", DELAY),
    _m("28D", "Atraso do controle do linear — 430/440 MHz", DELAY),
    _m("28E", "Atraso do controle do linear — 1,2 GHz", DELAY),
    _m("29A", "Repetir a reprodução de mensagens", ONOFF),
    _m("29B", "Intervalo entre repetições",
       {f"{i:02d}": f"{i} s" for i in range(61)}),
    _m("30", "Prioridade do manipulador sobre a reprodução", ONOFF),
    _m("31", "Pitch de CW (RX) / sidetone (TX)",
       {f"{i:02d}": f"{400 + 50 * i} Hz" for i in range(13)}),
    _m("32", "Tempo de subida do CW", _opts("1 ms", "2 ms", "4 ms", "6 ms")),
    _m("33", "Relação ponto/traço do keyer",
       {"00": "AUTO", **{f"{i:02d}": f"{2.4 + i / 10:.1f}"
                         for i in range(1, 17)}}),
    _m("34", "Relação automática reversa do keyer", ONOFF),
    _m("35", "Modo bug key", ONOFF),
    _m("36", "TX CW automático no modo SSB", ONOFF),
    _m("37", "Correção de frequência ao passar de SSB para CW", ONOFF),
    _m("38", "Shift de FSK", _opts("170 Hz", "200 Hz", "425 Hz", "850 Hz")),
    _m("39", "Polaridade de chaveamento FSK", _opts("NORMAL", "INVERTIDA")),
    _m("40", "Frequência do tom FSK", _opts("1275 Hz", "2125 Hz")),
    _m("41", "Ganho do microfone em FM", _opts("LOW", "MID", "HIGH")),
    _m("42", "Modo do subtom em FM", _opts("BURST", "CONT")),
    _m("43", "Offset automático de repetidora", ONOFF),
    _m("44", "Manter TX: tom de 1750 Hz", ONOFF),
    _m("45A", "Memória de número DTMF (valor bruto, ver manual)"),
    _m("45B", "Velocidade de TX do número DTMF", _opts("SLOW", "FAST")),
    _m("45C", "Pausa do número DTMF",
       _opts("100 ms", "250 ms", "500 ms", "750 ms", "1000 ms", "1500 ms",
             "2000 ms")),
    _m("45D", "Controle remoto pelo microfone", ONOFF),
    _m("46", "Banda do TNC interno", _opts("MAIN", "SUB")),
    _m("47", "Velocidade do TNC interno", _opts("1200 bps", "9600 bps")),
    _m("48", "Banda de detecção DCD", _opts("Banda do TNC", "MAIN e SUB")),
    _m("49A", "Modo Packet Cluster Tune", _opts("MANUAL", "AUTO")),
    _m("49B", "Tom de confirmação do Packet Cluster",
       _opts("OFF", "MORSE", "VOZ")),
    _m("50A", "Largura do filtro para packet", ONOFF),
    _m("50B", "Nível de entrada de AF para packet",
       {str(i): str(i) for i in range(10)}),
    _m("50C", "Nível de saída de AF (MAIN) para packet",
       {str(i): str(i) for i in range(10)}),
    _m("50D", "Nível de saída de AF (SUB) para packet",
       {str(i): str(i) for i in range(10)}),
    _m("50E", "Banda do TNC externo", _opts("MAIN", "SUB")),
    _m("50F", "Velocidade do TNC externo", _opts("1200 bps", "9600 bps")),
    _m("51A", "Tecla PF do painel", PF_CODES),
    _m("51B", "Tecla PF1 (CALL) do microfone", PF_CODES),
    _m("51C", "Tecla PF2 (VFO) do microfone", PF_CODES),
    _m("51D", "Tecla PF3 (MR) do microfone", PF_CODES),
    _m("51E", "Tecla PF4 (PF) do microfone", PF_CODES),
    _m("52", "Transferir split em operação mestre/escravo", ONOFF),
    _m("53", "Gravar split transferido nos VFOs de destino", ONOFF),
    _m("54", "Inibir TX", ONOFF),
    _m("55", "Modo de comunicação packet (desligar com TC 1)", ONOFF),
    _m("56", "Velocidade da porta COM",
       _opts("4800", "9600", "19200", "38400", "57600")),
    _m("57", "Desligamento automático (APO)",
       _opts("OFF", "60 min", "120 min", "180 min")),
    _m("58", "Fonte do RC-2000 no modo fácil", _opts("FONT1", "FONT2")),
    _m("59", "Contraste do RC-2000 / matriz de pontos",
       {f"{i:02d}": str(i) for i in range(1, 17)}),
    _m("60", "Modo do display do RC-2000", _opts("NEGATIVO", "POSITIVO")),
    _m("61A", "Modo repetidora", _opts("OFF", "LOCKED", "CROSS")),
    _m("61B", "Manter TX da repetidora", ONOFF),
    _m("61C", "Código de ID do controle remoto (000-999)"),
    _m("61D", "Sinal de confirmação no controle remoto externo", ONOFF),
    _m("61E", "Controle remoto externo", ONOFF),
    _m("62A", "Indicativo do comandante (Sky Command II+)"),
    _m("62B", "Indicativo do transportador (Sky Command II+)"),
    _m("62C", "Tom do Sky Command II+ (nº do tom, 2 dígitos)"),
    _m("62D", "Velocidade do Sky Command II+", _opts("1200", "9600")),
    _m("62E", "Modo do Sky Command II+",
       _opts("OFF", "CLIENT", "COMMANDER", "TRANSPORTER")),
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
