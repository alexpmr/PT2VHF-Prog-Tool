"""Interface gráfica (Tkinter) do programador do Kenwood TS-2000."""

from __future__ import annotations

import dataclasses
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import common.tkthreads  # noqa: F401

from . import __version__
from . import protocol as P
from .fileio import (Codeplug, export_csv, import_csv, load_project,
                     save_project)
from .lcd import DisplayWindow
from .menus import MenuDef, load_menu_defs, save_menu_defs
from .radio import (BAUD_RATES, TS2000, Cancelled, RadioError, list_ports)
from .status import RadioStatus

APP_TITLE = "PT2VHF Prog Tool — Kenwood TS-2000"
FILE_TYPES = [("Projeto TS-2000", "*.ts2k"), ("Todos", "*.*")]
CSV_TYPES = [("CSV", "*.csv"), ("Todos", "*.*")]


def mhz(hz: int) -> str:
    return f"{hz / 1e6:.5f}" if hz else ""


def parse_mhz(text: str) -> int:
    text = text.strip().replace(",", ".")
    if not text:
        return 0
    try:
        return round(float(text) * 1e6)
    except ValueError:
        raise ValueError(f"Frequência inválida: {text!r}") from None


# =========================================================== diálogo memória

class MemoryDialog(tk.Toplevel):
    def __init__(self, master, mem: P.Memory):
        super().__init__(master)
        self.title(f"Canal {mem.number:03d}")
        self.transient(master)
        self.resizable(False, False)
        self.result: P.Memory | None = None
        self.mem = mem
        pscan = P.is_program_scan(mem.number)
        src = mem if not mem.empty else P.Memory(
            mem.number, False, 145_000_000, 4, step=6)

        f = ttk.Frame(self, padding=12)
        f.grid(sticky="nsew")
        row = 0

        def add(label: str, widget: tk.Widget, col: int = 0) -> None:
            nonlocal row
            ttk.Label(f, text=label).grid(row=row, column=col, sticky="w",
                                          padx=(0, 8), pady=3)
            widget.grid(row=row, column=col + 1, sticky="we", pady=3)
            row += 1

        self.v_name = tk.StringVar(value=src.name)
        e_name = ttk.Entry(f, textvariable=self.v_name, width=12)
        add("Nome (até 8):", e_name)

        self.v_freq = tk.StringVar(value=mhz(src.freq))
        add("Início (MHz):" if pscan else "Freq. RX (MHz):",
            ttk.Entry(f, textvariable=self.v_freq, width=14))

        self.v_mode = tk.StringVar(value=P.MODES[src.mode])
        cb_mode = ttk.Combobox(f, textvariable=self.v_mode, state="readonly",
                               values=list(P.MODES.values()), width=10)
        cb_mode.bind("<<ComboboxSelected>>", lambda e: self._update_steps())
        add("Modo:", cb_mode)

        self.v_tx = tk.StringVar(
            value=mhz(src.tx_freq) if (src.split or pscan) else "")
        add("Fim (MHz):" if pscan else "Split: freq. TX (MHz):",
            ttk.Entry(f, textvariable=self.v_tx, width=14))
        if not pscan:
            ttk.Label(f, text="(vazio = sem split)", foreground="gray").grid(
                row=row - 1, column=2, sticky="w", padx=6)
        self.v_txmode = tk.StringVar(value=P.MODES.get(src.tx_mode, "(igual)"))
        cb_txmode = ttk.Combobox(f, textvariable=self.v_txmode,
                                 state="readonly", width=10,
                                 values=["(igual)", *P.MODES.values()])
        if not pscan:
            add("Modo TX (split):", cb_txmode)

        self.v_shift = tk.StringVar(value=P.SHIFTS[src.shift])
        add("Shift:", ttk.Combobox(f, textvariable=self.v_shift,
                                   state="readonly", width=10,
                                   values=list(P.SHIFTS.values())))
        self.v_offset = tk.StringVar(value=f"{src.offset / 1e6:.3f}")
        add("Offset (MHz):", ttk.Entry(f, textvariable=self.v_offset,
                                       width=14))
        self.v_rev = tk.BooleanVar(value=src.reverse)
        add("Reverse:", ttk.Checkbutton(f, variable=self.v_rev))

        self.v_tmode = tk.StringVar(value=P.TONE_MODES[src.tone_mode])
        add("Tipo de tom:", ttk.Combobox(f, textvariable=self.v_tmode,
                                         state="readonly", width=10,
                                         values=list(P.TONE_MODES.values())))
        tone_vals = [f"{t:.1f}" for t in P.TONES]
        self.v_tone = tk.StringVar(value=tone_vals[src.tone - 1])
        add("Tom (Hz):", ttk.Combobox(f, textvariable=self.v_tone,
                                      state="readonly", width=10,
                                      values=tone_vals))
        self.v_ctcss = tk.StringVar(value=tone_vals[src.ctcss - 1])
        add("CTCSS (Hz):", ttk.Combobox(f, textvariable=self.v_ctcss,
                                        state="readonly", width=10,
                                        values=tone_vals))
        dcs_vals = [f"{c:03d}" for c in P.DCS_CODES]
        self.v_dcs = tk.StringVar(value=dcs_vals[src.dcs])
        add("DCS:", ttk.Combobox(f, textvariable=self.v_dcs, state="readonly",
                                 width=10, values=dcs_vals))

        self.v_step = tk.StringVar()
        self.cb_step = ttk.Combobox(f, textvariable=self.v_step,
                                    state="readonly", width=10)
        add("Passo (kHz):", self.cb_step)
        self._update_steps(src.step)

        self.v_group = tk.StringVar(value=str(src.group))
        add("Grupo:", ttk.Spinbox(f, from_=0, to=9, textvariable=self.v_group,
                                  width=8, state="readonly"))
        self.v_lock = tk.BooleanVar(value=src.lockout)
        add("Lockout (pular):", ttk.Checkbutton(f, variable=self.v_lock))

        btns = ttk.Frame(f)
        btns.grid(row=row, column=0, columnspan=3, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(
            side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        e_name.focus_set()
        self.grab_set()

    def _update_steps(self, index: int | None = None) -> None:
        mode = P.MODE_BY_NAME[self.v_mode.get()]
        steps = [f"{s:g}" for s in P.steps_for_mode(mode)]
        cur = self.v_step.get()
        self.cb_step["values"] = steps
        if index is not None and index < len(steps):
            self.v_step.set(steps[index])
        elif cur not in steps:
            self.v_step.set(steps[0])

    def _ok(self) -> None:
        try:
            mode = P.MODE_BY_NAME[self.v_mode.get()]
            txm = self.v_txmode.get()
            m = P.Memory(
                number=self.mem.number, empty=False,
                freq=parse_mhz(self.v_freq.get()), mode=mode,
                tx_freq=parse_mhz(self.v_tx.get()),
                tx_mode=P.MODE_BY_NAME.get(txm, 0),
                shift={v: k for k, v in P.SHIFTS.items()}[self.v_shift.get()],
                offset=parse_mhz(self.v_offset.get() or "0"),
                reverse=self.v_rev.get(),
                tone_mode={v: k for k, v in
                           P.TONE_MODES.items()}[self.v_tmode.get()],
                tone=P.TONES.index(float(self.v_tone.get())) + 1,
                ctcss=P.TONES.index(float(self.v_ctcss.get())) + 1,
                dcs=P.DCS_CODES.index(int(self.v_dcs.get())),
                step=[f"{s:g}" for s in
                      P.steps_for_mode(mode)].index(self.v_step.get()),
                group=int(self.v_group.get()), lockout=self.v_lock.get(),
                name=self.v_name.get().rstrip(),
            )
            if m.tx_mode == m.mode:
                m.tx_mode = 0
            m.validate()
        except ValueError as e:
            messagebox.showerror("Valor inválido", str(e), parent=self)
            return
        self.result = m
        self.destroy()


# ============================================================= diálogo menu

class MenuValueDialog(tk.Toplevel):
    def __init__(self, master, d: MenuDef, raw: str | None):
        super().__init__(master)
        self.title(f"Menu {d.label}")
        self.transient(master)
        self.resizable(False, False)
        self.result: str | None = None
        self.d = d
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both")
        ttk.Label(f, text=f"{d.label} — {d.name}",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Comando: EX{d.ex:03d}{d.sub:02d}00<valor>;",
                  foreground="gray").pack(anchor="w", pady=(0, 8))
        self.v = tk.StringVar()
        if d.options:
            self.labels = [f"{lab}  [{k}]" for k, lab in d.options.items()]
            cur = (f"{d.options[raw]}  [{raw}]" if raw in d.options
                   else self.labels[0])
            self.v.set(cur)
            w = ttk.Combobox(f, textvariable=self.v, values=self.labels,
                             state="readonly", width=30)
        else:
            self.v.set(raw or "")
            w = ttk.Entry(f, textvariable=self.v, width=20)
            ttk.Label(f, text="Valor bruto (dígitos enviados ao rádio):"
                      ).pack(anchor="w")
        w.pack(anchor="w", fill="x")
        w.focus_set()
        b = ttk.Frame(f)
        b.pack(anchor="e", pady=(10, 0))
        ttk.Button(b, text="OK", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(
            side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _ok(self) -> None:
        txt = self.v.get().strip()
        if self.d.options:
            value = txt.rsplit("[", 1)[-1].rstrip("]")
        else:
            value = txt
        if not value or not value.isalnum():
            messagebox.showerror("Valor inválido",
                                 "Informe apenas letras/dígitos.", parent=self)
            return
        self.result = value
        self.destroy()


# ===================================================================== app

class App(tk.Toplevel):
    MEM_COLS = [
        ("ch", "Canal", 52), ("name", "Nome", 80), ("rx", "RX MHz", 95),
        ("mode", "Modo", 55), ("tx", "TX/Fim MHz", 95), ("shift", "Shift", 55),
        ("offset", "Offset", 65), ("tmode", "Tom", 55), ("tone", "Tom Hz", 60),
        ("ctcss", "CTCSS", 55), ("dcs", "DCS", 45), ("rev", "Rev", 35),
        ("step", "Passo", 50), ("grp", "Grp", 35), ("lock", "Lock", 40),
    ]

    def __init__(self, master=None):
        super().__init__(master)
        self.title(APP_TITLE)
        self.geometry("1240x700")
        self.minsize(900, 500)

        self.cp = Codeplug()
        self.defs, self.defs_src = load_menu_defs()
        self.dirty_mem: set[int] = set()
        self.dirty_menu: set[str] = set()
        self.path: str | None = None
        self.modified = False
        self.clipboard: list[P.Memory] = []

        self.q: queue.Queue = queue.Queue()
        self.radio = TS2000(log=lambda d, t: self.q.put(("log", d, t)))
        self.worker: threading.Thread | None = None
        self.cancel_ev = threading.Event()
        self.display: DisplayWindow | None = None
        self.monitor_stop = threading.Event()
        self.monitor_thread: threading.Thread | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self._poll)
        self._log("INFO", f"Definições de menu: {self.defs_src}")

    # ------------------------------------------------------------ layout
    def _build_menu(self) -> None:
        mb = tk.Menu(self)
        m = tk.Menu(mb, tearoff=False)
        m.add_command(label="Novo", command=self.file_new, accelerator="Ctrl+N")
        m.add_command(label="Abrir...", command=self.file_open,
                      accelerator="Ctrl+O")
        m.add_command(label="Salvar", command=self.file_save,
                      accelerator="Ctrl+S")
        m.add_command(label="Salvar como...", command=self.file_save_as)
        m.add_separator()
        m.add_command(label="Importar memórias (CSV)...",
                      command=self.import_csv)
        m.add_command(label="Exportar memórias (CSV)...",
                      command=self.export_csv)
        m.add_separator()
        m.add_command(label="Sair", command=self.on_close)
        mb.add_cascade(label="Arquivo", menu=m)

        r = tk.Menu(mb, tearoff=False)
        r.add_command(label="Conectar / Desconectar",
                      command=self.toggle_connect)
        r.add_separator()
        r.add_command(label="Ler tudo do rádio", command=self.download_all)
        r.add_command(label="Ler somente memórias",
                      command=lambda: self.download(True, False))
        r.add_command(label="Ler somente menus",
                      command=lambda: self.download(False, True))
        r.add_separator()
        r.add_command(label="Gravar tudo no rádio", command=self.upload_all)
        r.add_command(label="Gravar somente memórias",
                      command=lambda: self.upload(True, False))
        r.add_command(label="Gravar somente menus",
                      command=lambda: self.upload(False, True))
        r.add_separator()
        r.add_command(label="Display em tempo real", command=self.open_display)
        mb.add_cascade(label="Rádio", menu=r)

        mm = tk.Menu(mb, tearoff=False)
        mm.add_command(label="Varrer menus no rádio...",
                       command=self.scan_menus)
        mm.add_command(label="Exportar definições de menus...",
                       command=self.export_defs)
        mm.add_command(label="Carregar definições de menus...",
                       command=self.import_defs)
        mb.add_cascade(label="Menus", menu=mm)

        h = tk.Menu(mb, tearoff=False)
        h.add_command(label="Versões e atualizações",
                      command=self.show_versions)
        h.add_command(label="Sobre", command=self.about)
        mb.add_cascade(label="Ajuda", menu=h)
        self.config(menu=mb)
        self.bind("<Control-n>", lambda e: self.file_new())
        self.bind("<Control-o>", lambda e: self.file_open())
        self.bind("<Control-s>", lambda e: self.file_save())

    def _build_toolbar(self) -> None:
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        ttk.Label(tb, text="Porta:").pack(side="left")
        self.v_port = tk.StringVar()
        self.cb_port = ttk.Combobox(tb, textvariable=self.v_port, width=16)
        self.cb_port.pack(side="left", padx=(4, 2))
        ttk.Button(tb, text="↻", width=3, command=self.refresh_ports).pack(
            side="left")
        ttk.Label(tb, text="Baud:").pack(side="left", padx=(10, 0))
        self.v_baud = tk.StringVar(value="9600")
        ttk.Combobox(tb, textvariable=self.v_baud, width=7, state="readonly",
                     values=[str(b) for b in BAUD_RATES]).pack(side="left",
                                                               padx=4)
        self.v_stop = tk.StringVar(value="1")
        ttk.Label(tb, text="Stop:").pack(side="left")
        ttk.Combobox(tb, textvariable=self.v_stop, width=3, state="readonly",
                     values=["1", "2"]).pack(side="left", padx=4)
        self.v_rtscts = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb, text="RTS/CTS", variable=self.v_rtscts).pack(
            side="left", padx=4)
        self.btn_conn = ttk.Button(tb, text="Conectar",
                                   command=self.toggle_connect)
        self.btn_conn.pack(side="left", padx=6)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y",
                                                  padx=8)
        self.btn_dl = ttk.Button(tb, text="⬇ Ler do rádio",
                                 command=self.download_all)
        self.btn_dl.pack(side="left")
        self.btn_ul = ttk.Button(tb, text="⬆ Gravar no rádio",
                                 command=self.upload_all)
        self.btn_ul.pack(side="left", padx=4)
        self.v_only_changed = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb, text="Somente alterados",
                        variable=self.v_only_changed).pack(side="left", padx=4)
        self.v_verify = tk.BooleanVar(value=False)
        ttk.Checkbutton(tb, text="Verificar gravação",
                        variable=self.v_verify).pack(side="left")
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y",
                                                  padx=8)
        ttk.Button(tb, text="Display LCD", command=self.open_display).pack(
            side="left")
        self.refresh_ports()

    def _build_tabs(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8)

        # ---- memórias
        fm = ttk.Frame(self.nb, padding=4)
        self.nb.add(fm, text="Memórias")
        bar = ttk.Frame(fm)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in [("Editar...", self.mem_edit),
                          ("Apagar", self.mem_delete),
                          ("Copiar", self.mem_copy), ("Colar", self.mem_paste),
                          ("Ler selecionados", self.mem_read_selected),
                          ("Gravar selecionados", self.mem_write_selected)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.v_show_empty = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Mostrar vazios", variable=self.v_show_empty,
                        command=self.refresh_memories).pack(side="right")
        ttk.Label(bar, text="290-299 = limites da varredura programada (P0-P9)",
                  foreground="gray").pack(side="right", padx=10)

        tv_frame = ttk.Frame(fm)
        tv_frame.pack(fill="both", expand=True)
        self.tv_mem = ttk.Treeview(tv_frame, columns=[c[0] for c in
                                                      self.MEM_COLS],
                                   show="headings", selectmode="extended")
        for cid, title, w in self.MEM_COLS:
            self.tv_mem.heading(cid, text=title)
            self.tv_mem.column(cid, width=w, anchor="w", stretch=cid == "name")
        sb = ttk.Scrollbar(tv_frame, orient="vertical",
                           command=self.tv_mem.yview)
        self.tv_mem.configure(yscrollcommand=sb.set)
        self.tv_mem.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv_mem.tag_configure("empty", foreground="#999999")
        self.tv_mem.tag_configure("pscan", background="#eaf2ff")
        self.tv_mem.tag_configure("dirty", background="#fff3b0")
        self.tv_mem.bind("<Double-1>", lambda e: self.mem_edit())
        self.tv_mem.bind("<Return>", lambda e: self.mem_edit())
        self.tv_mem.bind("<Delete>", lambda e: self.mem_delete())
        self.tv_mem.bind("<Control-c>", lambda e: self.mem_copy())
        self.tv_mem.bind("<Control-v>", lambda e: self.mem_paste())

        # ---- menus
        fmn = ttk.Frame(self.nb, padding=4)
        self.nb.add(fmn, text="Menus")
        bar = ttk.Frame(fmn)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Editar...", command=self.menu_edit).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Ler selecionados",
                   command=self.menu_read_selected).pack(side="left", padx=2)
        ttk.Button(bar, text="Gravar selecionados",
                   command=self.menu_write_selected).pack(side="left", padx=2)
        ttk.Button(bar, text="Varrer menus...", command=self.scan_menus).pack(
            side="left", padx=2)
        ttk.Label(bar, text="Tabela conforme o manual do TS-2000",
                  foreground="gray").pack(side="right")
        tvf = ttk.Frame(fmn)
        tvf.pack(fill="both", expand=True)
        cols = [("label", "Menu", 60), ("name", "Descrição", 380),
                ("value", "Valor", 160), ("raw", "Bruto", 70),
                ("cmd", "EX", 90), ("ok", "✓", 30)]
        self.tv_menu = ttk.Treeview(tvf, columns=[c[0] for c in cols],
                                    show="headings", selectmode="extended")
        for cid, title, w in cols:
            self.tv_menu.heading(cid, text=title)
            self.tv_menu.column(cid, width=w, anchor="w",
                                stretch=cid == "name")
        sb2 = ttk.Scrollbar(tvf, orient="vertical",
                            command=self.tv_menu.yview)
        self.tv_menu.configure(yscrollcommand=sb2.set)
        self.tv_menu.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.tv_menu.tag_configure("dirty", background="#fff3b0")
        self.tv_menu.tag_configure("unknown", foreground="#999999")
        self.tv_menu.bind("<Double-1>", lambda e: self.menu_edit())
        self.tv_menu.bind("<Return>", lambda e: self.menu_edit())

        # ---- log
        fl = ttk.Frame(self.nb, padding=4)
        self.nb.add(fl, text="Log CAT")
        bar = ttk.Frame(fl)
        bar.pack(fill="x")
        self.v_log_cat = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Registrar tráfego serial",
                        variable=self.v_log_cat).pack(side="left")
        ttk.Button(bar, text="Limpar",
                   command=lambda: self.txt_log.delete("1.0", "end")).pack(
            side="right")
        self.txt_log = tk.Text(fl, height=10, font=("TkFixedFont", 9),
                               wrap="none")
        sb3 = ttk.Scrollbar(fl, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb3.set)
        self.txt_log.pack(side="left", fill="both", expand=True, pady=4)
        sb3.pack(side="right", fill="y", pady=4)

    def _build_status(self) -> None:
        sf = ttk.Frame(self, padding=(8, 4))
        sf.pack(fill="x")
        self.v_status = tk.StringVar(value="Desconectado")
        ttk.Label(sf, textvariable=self.v_status).pack(side="left")
        self.btn_cancel = ttk.Button(sf, text="Cancelar", state="disabled",
                                     command=self.cancel_ev.set)
        self.btn_cancel.pack(side="right")
        self.pb = ttk.Progressbar(sf, length=260, mode="determinate")
        self.pb.pack(side="right", padx=8)

    # ------------------------------------------------------------- views
    def refresh_all(self) -> None:
        self.refresh_memories()
        self.refresh_menus()
        self._update_title()

    def _mem_values(self, m: P.Memory) -> list[str]:
        if m.empty:
            return [f"{m.number:03d}"] + [""] * (len(self.MEM_COLS) - 1)
        steps = P.steps_for_mode(m.mode)
        tx = ""
        if P.is_program_scan(m.number):
            tx = mhz(m.tx_freq)
        elif m.split:
            tx = mhz(m.tx_freq) + (f" {P.MODES[m.tx_mode]}" if m.tx_mode
                                   else "")
        tm = m.tone_mode
        return [
            f"{m.number:03d}", m.name, mhz(m.freq), P.MODES[m.mode], tx,
            P.SHIFTS[m.shift] if m.shift else "",
            f"{m.offset / 1e6:g}" if m.offset else "",
            P.TONE_MODES[tm] if tm else "",
            f"{P.TONES[m.tone - 1]:.1f}" if tm == 1 else "",
            f"{P.TONES[m.ctcss - 1]:.1f}" if tm == 2 else "",
            f"{P.DCS_CODES[m.dcs]:03d}" if tm == 3 else "",
            "R" if m.reverse else "", f"{steps[m.step]:g}", str(m.group),
            "L" if m.lockout else "",
        ]

    def _mem_tags(self, m: P.Memory) -> tuple:
        tags = []
        if m.number in self.dirty_mem:
            tags.append("dirty")
        if m.empty:
            tags.append("empty")
        if P.is_program_scan(m.number):
            tags.append("pscan")
        return tuple(tags)

    def refresh_memories(self) -> None:
        sel = set(self.tv_mem.selection())
        self.tv_mem.delete(*self.tv_mem.get_children())
        for n, m in self.cp.memories.items():
            if m.empty and not self.v_show_empty.get() and \
                    n not in self.dirty_mem:
                continue
            iid = str(n)
            self.tv_mem.insert("", "end", iid=iid, values=self._mem_values(m),
                               tags=self._mem_tags(m))
        keep = [i for i in sel if self.tv_mem.exists(i)]
        if keep:
            self.tv_mem.selection_set(keep)
        used = sum(1 for m in self.cp.memories.values() if not m.empty)
        self.nb.tab(0, text=f"Memórias ({used}/{P.NUM_MEMORIES})")

    def refresh_memory(self, n: int) -> None:
        iid = str(n)
        m = self.cp.memories[n]
        if self.tv_mem.exists(iid):
            self.tv_mem.item(iid, values=self._mem_values(m),
                             tags=self._mem_tags(m))
        else:
            self.refresh_memories()

    def _all_defs(self) -> list[MenuDef]:
        """Definições + menus presentes no projeto mas sem definição."""
        known = {d.key for d in self.defs}
        extra = [MenuDef(f"EX{k[:3]}/{k[3:]}", int(k[:3]), int(k[3:]),
                         "(sem definição — valor bruto)")
                 for k in sorted(self.cp.menus) if k not in known]
        return self.defs + extra

    def refresh_menus(self) -> None:
        sel = set(self.tv_menu.selection())
        self.tv_menu.delete(*self.tv_menu.get_children())
        for d in self._all_defs():
            raw = self.cp.menus.get(d.key)
            tags = []
            if d.key in self.dirty_menu:
                tags.append("dirty")
            if raw is None:
                tags.append("unknown")
            self.tv_menu.insert(
                "", "end", iid=d.key, tags=tuple(tags),
                values=[d.label, d.name, d.display(raw) if raw is not None
                        else "—", raw or "", f"EX{d.ex:03d}{d.sub:02d}00",
                        "✓" if d.verified else ""])
        keep = [i for i in sel if self.tv_menu.exists(i)]
        if keep:
            self.tv_menu.selection_set(keep)

    def _update_title(self) -> None:
        name = os.path.basename(self.path) if self.path else "sem título"
        self.title(f"{'*' if self.modified else ''}{name} — {APP_TITLE}")

    def _set_modified(self, value: bool = True) -> None:
        self.modified = value
        self._update_title()

    # --------------------------------------------------------------- log
    def _log(self, direction: str, text: str) -> None:
        if direction in ("TX", "RX") and not self.v_log_cat.get():
            return
        arrow = {"TX": "→", "RX": "←"}.get(direction, "•")
        self.txt_log.insert("end", f"{arrow} {text}\n")
        lines = int(self.txt_log.index("end-1c").split(".")[0])
        if lines > 5000:
            self.txt_log.delete("1.0", f"{lines - 5000}.0")
        self.txt_log.see("end")

    def _poll(self) -> None:
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._log(msg[1], msg[2])
                elif kind == "progress":
                    done, total, text = msg[1:]
                    self.pb["maximum"] = max(total, 1)
                    self.pb["value"] = done
                    self.v_status.set(text)
                elif kind == "status":
                    if self.display:
                        self.display.update_status(msg[1])
                elif kind == "done":
                    callback, result, error = msg[1:]
                    self._finish_task(callback, result, error)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    # ----------------------------------------------------- tarefas em thread
    def _busy(self) -> bool:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Aguarde a operação em andamento.", parent=self)
            return True
        return False

    def run_task(self, func, on_done, need_radio: bool = True) -> None:
        if self._busy():
            return
        if need_radio and not self.radio.connected:
            messagebox.showwarning(APP_TITLE, "Conecte-se ao rádio primeiro.", parent=self)
            return
        self.cancel_ev.clear()
        self.btn_cancel.configure(state="normal")
        self._set_controls(False)

        def progress(done, total, text):
            self.q.put(("progress", done, total, text))

        def target():
            try:
                result = func(progress, self.cancel_ev)
                self.q.put(("done", on_done, result, None))
            except Exception as e:      # noqa: BLE001 — reportado na GUI
                self.q.put(("done", on_done, None, e))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _finish_task(self, callback, result, error) -> None:
        self.btn_cancel.configure(state="disabled")
        self._set_controls(True)
        if isinstance(error, Cancelled):
            self.v_status.set("Operação cancelada")
            self._log("INFO", "Operação cancelada pelo usuário")
            return
        if error is not None:
            self.v_status.set(f"Erro: {error}")
            self._log("ERRO", str(error))
            messagebox.showerror(APP_TITLE, str(error), parent=self)
            return
        callback(result)

    def _set_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in (self.btn_conn, self.btn_dl, self.btn_ul):
            b.configure(state=state)

    def _report_errors(self, title: str, errors: list[str]) -> None:
        if not errors:
            return
        for e in errors:
            self._log("ERRO", e)
        shown = "\n".join(errors[:15])
        if len(errors) > 15:
            shown += f"\n... e mais {len(errors) - 15} (veja o Log CAT)"
        messagebox.showwarning(title, shown, parent=self)

    # ----------------------------------------------------------- conexão
    def refresh_ports(self) -> None:
        ports = list_ports()
        self.cb_port["values"] = ports
        if self.v_port.get() not in ports:
            self.v_port.set(ports[0] if ports else "")

    def toggle_connect(self) -> None:
        if self._busy():
            return
        if self.radio.connected:
            self.stop_monitor()
            self.radio.disconnect()
            self._push_status(RadioStatus())
            self.btn_conn.configure(text="Conectar")
            self.v_status.set("Desconectado")
            self._log("INFO", "Desconectado")
            return
        port = self.v_port.get().strip()
        if not port:
            messagebox.showwarning(APP_TITLE, "Selecione a porta serial.", parent=self)
            return
        baud, rtscts, stop = (int(self.v_baud.get()), self.v_rtscts.get(),
                              int(self.v_stop.get()))

        def task(progress, cancel):
            progress(0, 1, f"Conectando em {port}...")
            return self.radio.connect(port, baud, rtscts, stop)

        def done(rid):
            self.btn_conn.configure(text="Desconectar")
            self.v_status.set(f"Conectado: TS-2000 ({rid}) em {port}")
            self.pb["value"] = 0
            self._log("INFO", f"Conectado em {port} @ {baud}")
            if self.display:
                self.start_monitor()

        self.run_task(task, done, need_radio=False)

    # ---------------------------------------------------- download/upload
    def download_all(self) -> None:
        self.download(True, True)

    def download(self, memories: bool, menus: bool,
                 numbers: list[int] | None = None,
                 defs: list[MenuDef] | None = None) -> None:
        nums = numbers if numbers is not None else (
            list(range(P.NUM_MEMORIES)) if memories else [])
        mdefs = defs if defs is not None else (
            self._all_defs() if menus else [])

        def task(progress, cancel):
            mems = self.radio.download_memories(nums, progress, cancel) \
                if nums else {}
            vals, errs = self.radio.download_menus(mdefs, progress, cancel) \
                if mdefs else ({}, [])
            return mems, vals, errs

        def done(result):
            mems, vals, errs = result
            for n, m in mems.items():
                self.cp.memories[n] = m
                self.dirty_mem.discard(n)
            for k, v in vals.items():
                self.cp.menus[k] = v
                self.dirty_menu.discard(k)
            self.refresh_all()
            if mems or vals:
                self._set_modified()
            self.v_status.set(f"Leitura concluída: {len(mems)} canais, "
                              f"{len(vals)} menus")
            self._report_errors("Menus não lidos", errs)

        self.run_task(task, done)

    def upload_all(self) -> None:
        self.upload(True, True)

    def upload(self, memories: bool, menus: bool,
               numbers: list[int] | None = None,
               keys: list[str] | None = None) -> None:
        only = self.v_only_changed.get()
        if numbers is None:
            numbers = sorted(self.dirty_mem) if only else \
                list(range(P.NUM_MEMORIES))
            numbers = numbers if memories else []
        if keys is None:
            keys = sorted(self.dirty_menu) if only else sorted(self.cp.menus)
            keys = keys if menus else []
        keys = [k for k in keys if k in self.cp.menus]
        if not numbers and not keys:
            messagebox.showinfo(APP_TITLE, "Nada para gravar." + (
                " (Somente alterados está marcado e não há alterações.)"
                if only else ""), parent=self)
            return
        n_erase = sum(1 for n in numbers if self.cp.memories[n].empty)
        msg = (f"Gravar no rádio {len(numbers)} canal(is) e {len(keys)} "
               f"menu(s)?")
        if n_erase:
            msg += f"\n\nAtenção: {n_erase} canal(is) vazio(s) serão APAGADOS."
        if not messagebox.askyesno("Confirmar gravação", msg, parent=self):
            return
        mems = [self.cp.memories[n] for n in numbers]
        defs_by_key = {d.key: d for d in self._all_defs()}
        items = [(defs_by_key[k], self.cp.menus[k]) for k in keys]
        verify = self.v_verify.get()

        def task(progress, cancel):
            errs = self.radio.upload_memories(mems, progress, cancel, verify) \
                if mems else []
            errs += self.radio.upload_menus(items, progress, cancel) \
                if items else []
            return errs

        def done(errs):
            failed_ch = {int(e[6:9]) for e in errs if e.startswith("Canal ")}
            for n in numbers:
                if n not in failed_ch:
                    self.dirty_mem.discard(n)
            failed_mn = {e for e in errs if e.startswith("Menu ")}
            for d, _ in items:
                if not any(e.startswith(f"Menu {d.label}:")
                           for e in failed_mn):
                    self.dirty_menu.discard(d.key)
            self.refresh_all()
            self.v_status.set(f"Gravação concluída ({len(errs)} erro(s))")
            self._report_errors("Erros na gravação", errs)

        self.run_task(task, done)

    def scan_menus(self) -> None:
        if not self.radio.connected:
            messagebox.showwarning(APP_TITLE, "Conecte-se ao rádio primeiro.", parent=self)
            return
        deep = messagebox.askyesnocancel(
            "Varrer menus",
            "Consulta EX000-EX099 e registra os menus que o rádio responder.\n"
            "Nada é gravado no rádio.\n\n"
            "Sim = incluir sub-menus 00-09 (mais lento)\n"
            "Não = apenas sub-menu 00", parent=self)
        if deep is None:
            return
        subs = range(10) if deep else range(1)

        def task(progress, cancel):
            return self.radio.scan_menus(range(100), subs, progress, cancel)

        def done(found):
            new = [k for k in found if k not in self.cp.menus]
            self.cp.menus.update(found)
            for k in found:
                self.dirty_menu.discard(k)
            self.refresh_menus()
            self._set_modified()
            self._log("INFO", f"Varredura: {len(found)} menus responderam; "
                      f"{len(new)} novos")
            messagebox.showinfo(APP_TITLE, f"{len(found)} menus responderam.", parent=self)

        self.run_task(task, done)

    # ---------------------------------------------------- ações memórias
    def _selected_numbers(self) -> list[int]:
        return sorted(int(i) for i in self.tv_mem.selection())

    def mem_edit(self) -> None:
        nums = self._selected_numbers()
        if not nums:
            return
        dlg = MemoryDialog(self, self.cp.memories[nums[0]])
        self.wait_window(dlg)
        if dlg.result:
            self.cp.memories[nums[0]] = dlg.result
            self.dirty_mem.add(nums[0])
            self.refresh_memories()
            self._set_modified()

    def mem_delete(self) -> None:
        nums = self._selected_numbers()
        nums = [n for n in nums if not self.cp.memories[n].empty]
        if not nums:
            return
        if not messagebox.askyesno(APP_TITLE,
                                   f"Apagar {len(nums)} canal(is)?", parent=self):
            return
        for n in nums:
            self.cp.memories[n] = P.Memory(number=n)
            self.dirty_mem.add(n)
        self.refresh_memories()
        self._set_modified()

    def mem_copy(self) -> None:
        self.clipboard = [self.cp.memories[n] for n in
                          self._selected_numbers()]
        self.v_status.set(f"{len(self.clipboard)} canal(is) copiado(s)")

    def mem_paste(self) -> None:
        nums = self._selected_numbers()
        if not self.clipboard or not nums:
            return
        start = nums[0]
        if start + len(self.clipboard) > P.NUM_MEMORIES:
            messagebox.showerror(APP_TITLE, "Não cabe a partir deste canal.", parent=self)
            return
        targets = range(start, start + len(self.clipboard))
        if any(not self.cp.memories[t].empty for t in targets) and \
                not messagebox.askyesno(APP_TITLE,
                                        "Sobrescrever canais existentes?", parent=self):
            return
        for src, t in zip(self.clipboard, targets):
            self.cp.memories[t] = src.copy_to(t)
            self.dirty_mem.add(t)
        self.refresh_memories()
        self._set_modified()

    def mem_read_selected(self) -> None:
        nums = self._selected_numbers()
        if nums:
            self.download(True, False, numbers=nums, defs=[])

    def mem_write_selected(self) -> None:
        nums = self._selected_numbers()
        if nums:
            self.upload(True, False, numbers=nums, keys=[])

    # ------------------------------------------------------- ações menus
    def _selected_defs(self) -> list[MenuDef]:
        sel = set(self.tv_menu.selection())
        return [d for d in self._all_defs() if d.key in sel]

    def menu_edit(self) -> None:
        defs = self._selected_defs()
        if not defs:
            return
        d = defs[0]
        dlg = MenuValueDialog(self, d, self.cp.menus.get(d.key))
        self.wait_window(dlg)
        if dlg.result is not None and dlg.result != self.cp.menus.get(d.key):
            self.cp.menus[d.key] = dlg.result
            self.dirty_menu.add(d.key)
            self.refresh_menus()
            self._set_modified()

    def menu_read_selected(self) -> None:
        defs = self._selected_defs()
        if defs:
            self.download(False, True, numbers=[], defs=defs)

    def menu_write_selected(self) -> None:
        defs = self._selected_defs()
        if defs:
            self.upload(False, True, numbers=[], keys=[d.key for d in defs])

    def export_defs(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="menus_ts2000.json",
            filetypes=[("JSON", "*.json")])
        if path:
            save_menu_defs(self.defs, path)
            self._log("INFO", f"Definições exportadas para {path}")

    def import_defs(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.defs, self.defs_src = load_menu_defs(path)
        except (OSError, ValueError, KeyError) as e:
            messagebox.showerror(APP_TITLE, f"Arquivo inválido: {e}", parent=self)
            return
        self.refresh_menus()
        self._log("INFO", f"Definições de menu: {path}")

    # ----------------------------------------------------------- arquivos
    def _confirm_discard(self) -> bool:
        if not self.modified:
            return True
        ans = messagebox.askyesnocancel(APP_TITLE,
                                        "Salvar as alterações do projeto?", parent=self)
        if ans is None:
            return False
        return self.file_save() if ans else True

    def file_new(self) -> None:
        if not self._confirm_discard():
            return
        self.cp = Codeplug()
        self.dirty_mem.clear()
        self.dirty_menu.clear()
        self.path = None
        self.modified = False
        self.refresh_all()

    def file_open(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=FILE_TYPES)
        if not path:
            return
        try:
            self.cp = load_project(path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            messagebox.showerror(APP_TITLE, f"Não foi possível abrir: {e}", parent=self)
            return
        self.path = path
        # tudo o que veio do arquivo é considerado "alterado" em relação
        # ao rádio, para que "Somente alterados" grave o projeto inteiro.
        self.dirty_mem = set(range(P.NUM_MEMORIES))
        self.dirty_menu = set(self.cp.menus)
        self.modified = False
        self.refresh_all()
        self._log("INFO", f"Aberto {path}")

    def file_save(self) -> bool:
        if not self.path:
            return self.file_save_as()
        try:
            save_project(self.cp, self.path)
        except OSError as e:
            messagebox.showerror(APP_TITLE, f"Erro ao salvar: {e}", parent=self)
            return False
        self._set_modified(False)
        self.v_status.set(f"Salvo em {self.path}")
        return True

    def file_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(defaultextension=".ts2k",
                                            filetypes=FILE_TYPES)
        if not path:
            return False
        self.path = path
        return self.file_save()

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=CSV_TYPES)
        if not path:
            return
        try:
            mems, errs = import_csv(path)
        except OSError as e:
            messagebox.showerror(APP_TITLE, str(e), parent=self)
            return
        for m in mems:
            self.cp.memories[m.number] = m
            self.dirty_mem.add(m.number)
        self.refresh_memories()
        self._set_modified()
        self.v_status.set(f"{len(mems)} canais importados")
        self._report_errors("Linhas ignoradas", errs)

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=CSV_TYPES)
        if path:
            n = export_csv(self.cp, path)
            self.v_status.set(f"{n} canais exportados para {path}")

    # -------------------------------------------------- display tempo real
    def open_display(self) -> None:
        if self.display:
            self.display.deiconify()
            self.display.lift()
            return
        self.display = DisplayWindow(self, on_close=self._display_closed)
        if self.radio.connected:
            self.start_monitor()

    def _display_closed(self) -> None:
        self.stop_monitor()
        self.display = None

    def _push_status(self, st: RadioStatus) -> None:
        self.q.put(("status", dataclasses.replace(st, extra=dict(st.extra))))

    def start_monitor(self) -> None:
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.monitor_stop.clear()
        st = RadioStatus()

        def loop():
            n = 0
            while not self.monitor_stop.is_set():
                busy = self.worker is not None and self.worker.is_alive()
                if busy or not self.radio.connected:
                    time.sleep(0.3)     # leitura/gravação tem prioridade
                    continue
                try:
                    self.radio.read_status(st, full=(n % 10 == 0))
                    self._push_status(st)
                except (RadioError, ValueError, OSError) as e:
                    self.q.put(("log", "ERRO", f"Display: {e}"))
                    time.sleep(1)
                n += 1
                self.monitor_stop.wait(0.15)

        self.monitor_thread = threading.Thread(target=loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitor(self) -> None:
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            self.monitor_thread = None

    # -------------------------------------------------------------- misc
    def show_versions(self) -> None:
        from common.update_ui import VersionDialog
        VersionDialog(self)

    def about(self) -> None:
        messagebox.showinfo(
            "Sobre",
            f"{APP_TITLE} v{__version__}\n\n"
            "Edita memórias (000-299) e menus do Kenwood TS-2000 e "
            "transfere pela porta serial (CAT).\n\n"
            "Comandos: MR/MW (memórias), EX (menus), ID, AI.", parent=self)

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_TITLE,
                                       "Operação em andamento. Sair mesmo?", parent=self):
                return
            self.cancel_ev.set()
        if not self._confirm_discard():
            return
        self.stop_monitor()
        if self.display:
            self.display.destroy()
            self.display = None
        try:
            self.radio.disconnect()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    app.bind("<Destroy>", lambda e: root.destroy() if e.widget is app
             else None)
    root.mainloop()


if __name__ == "__main__":
    main()
