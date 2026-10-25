"""Editor de memórias para rádios Icom em modo de clonagem."""

from __future__ import annotations

import csv
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import common.tkthreads  # noqa: F401

from . import clone as C
from .icf import read_icf, write_icf
from .models import (DTCS_CODES, DTCS_POLARITY, DUPLEX, SKIPS, TONE_SHORT,
                     TONES, IcomMemory, IcomModel, model_for_id)

SIMULATOR_PORT = "SIMULADOR"


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as lp
        ports = sorted(p.device for p in lp.comports())
    except Exception:
        ports = []
    return ports + [SIMULATOR_PORT]


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


def bank_label(b: int | None) -> str:
    return "—" if b is None else chr(65 + b)


# ============================================================ diálogo

class IcomMemoryDialog(tk.Toplevel):
    def __init__(self, master, model: IcomModel, mem: IcomMemory,
                 bank_names: list[str]):
        super().__init__(master)
        self.title(f"{model.name} — canal {mem.number:03d}")
        self.transient(master)
        self.resizable(False, False)
        self.model = model
        self.mem = mem
        self.result: IcomMemory | None = None
        src = mem if not mem.empty else IcomMemory(
            mem.number, False, 145_000_000, step=8,
            bank=None)

        f = ttk.Frame(self, padding=12)
        f.grid()
        self.row = 0
        col_l = ttk.Frame(f)
        col_r = ttk.Frame(f)
        col_l.grid(row=0, column=0, sticky="n", padx=(0, 16))
        col_r.grid(row=0, column=1, sticky="n")

        def add(parent, label, widget):
            r = parent.grid_size()[1]
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w",
                                               pady=3, padx=(0, 8))
            widget.grid(row=r, column=1, sticky="we", pady=3)

        def combo(parent, var, values, width=14):
            return ttk.Combobox(parent, textvariable=var, values=values,
                                state="readonly", width=width)

        self.v_name = tk.StringVar(value=src.name)
        e_name = ttk.Entry(col_l, textvariable=self.v_name, width=18)
        add(col_l, f"Nome (até {model.name_len}):", e_name)
        self.v_freq = tk.StringVar(value=mhz(src.freq))
        add(col_l, "Frequência (MHz):",
            ttk.Entry(col_l, textvariable=self.v_freq, width=18))
        self.mode_names = {model.modes[k]: k for k in model.edit_modes}
        if src.mode not in model.edit_modes:
            self.mode_names[model.modes.get(src.mode, str(src.mode))] = \
                src.mode
        self.v_mode = tk.StringVar(value=model.modes.get(src.mode, "FM"))
        cb_mode = combo(col_l, self.v_mode, list(self.mode_names))
        cb_mode.bind("<<ComboboxSelected>>", lambda e: self._dv_state())
        add(col_l, "Modo:", cb_mode)
        self.v_dup = tk.StringVar(value=DUPLEX[src.duplex])
        add(col_l, "Duplex:", combo(col_l, self.v_dup, list(DUPLEX.values())))
        self.v_off = tk.StringVar(value=f"{src.offset / 1e6:.4f}")
        add(col_l, "Offset (MHz):",
            ttk.Entry(col_l, textvariable=self.v_off, width=18))
        self.step_vals = {f"{s:g}": i for i, s in enumerate(model.steps) if s}
        self.v_step = tk.StringVar(
            value=f"{model.steps[src.step]:g}" if src.step < len(
                model.steps) and model.steps[src.step] else "5")
        add(col_l, "Passo (kHz):", combo(col_l, self.v_step,
                                         list(self.step_vals)))
        self.v_skip = tk.StringVar(value=SKIPS[src.skip])
        add(col_l, "Varredura:", combo(col_l, self.v_skip,
                                       list(SKIPS.values())))
        self.bank_vals = ["—"] + [f"{chr(65 + i)}  {bank_names[i]}"
                                  for i in range(model.num_banks)]
        self.v_bank = tk.StringVar(
            value=self.bank_vals[0 if src.bank is None else src.bank + 1])
        add(col_l, "Banco:", combo(col_l, self.v_bank, self.bank_vals, 20))
        self.v_bidx = tk.StringVar(value=str(src.bank_index))
        add(col_l, "Índice no banco:", ttk.Spinbox(
            col_l, from_=0, to=99, textvariable=self.v_bidx, width=8))

        tm = model.tmode_labels
        self.tmode_vals = {v: k for k, v in tm.items()}
        self.v_tmode = tk.StringVar(value=tm.get(src.tmode, "Off"))
        add(col_r, "Tom/silenciador:", combo(col_r, self.v_tmode,
                                             list(tm.values()), 18))
        tones = [f"{t:.1f}" for t in TONES]
        self.v_rtone = tk.StringVar(value=tones[src.rtone])
        add(col_r, "Tom TX (Hz):", combo(col_r, self.v_rtone, tones))
        self.v_ctone = tk.StringVar(value=tones[src.ctone])
        add(col_r, "Tom TSQL (Hz):", combo(col_r, self.v_ctone, tones))
        dcs = [f"{c:03d}" for c in DTCS_CODES]
        self.v_dtcs = tk.StringVar(value=dcs[src.dtcs])
        add(col_r, "DTCS:", combo(col_r, self.v_dtcs, dcs))
        self.v_pol = tk.StringVar(value=DTCS_POLARITY[src.dtcs_pol])
        add(col_r, "Polaridade DTCS:", combo(col_r, self.v_pol,
                                             list(DTCS_POLARITY.values())))

        ttk.Separator(col_r).grid(columnspan=2, sticky="we", pady=6)
        ttk.Label(col_r, text="D-STAR (modo DV)",
                  font=("TkDefaultFont", 9, "bold")).grid(columnspan=2,
                                                          sticky="w")
        self.v_ur = tk.StringVar(value=src.urcall)
        self.v_r1 = tk.StringVar(value=src.rpt1)
        self.v_r2 = tk.StringVar(value=src.rpt2)
        self.v_code = tk.StringVar(value=str(src.dv_code))
        self.dv_widgets = []
        for label, var in (("UR (URCALL):", self.v_ur),
                           ("RPT1 (acesso):", self.v_r1),
                           ("RPT2 (gateway):", self.v_r2)):
            w = ttk.Entry(col_r, textvariable=var, width=18)
            add(col_r, label, w)
            self.dv_widgets.append(w)
        w = ttk.Spinbox(col_r, from_=0, to=99, textvariable=self.v_code,
                        width=8)
        add(col_r, "Código digital:", w)
        self.dv_widgets.append(w)
        if model.key == "id51plus2":
            self.dsql_vals = {"Off": 0, "DSQL": 1, "CSQL": 2}
            self.v_dsql = tk.StringVar(
                value={v: k for k, v in self.dsql_vals.items()}[src.dsql])
            w = combo(col_r, self.v_dsql, list(self.dsql_vals))
            add(col_r, "Silenciador digital:", w)
            self.dv_widgets.append(w)
        else:
            self.v_dsql = None

        b = ttk.Frame(f)
        b.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(b, text="OK", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(
            side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._dv_state()
        e_name.focus_set()
        self.grab_set()

    def _dv_state(self) -> None:
        state = "normal" if self.v_mode.get() == "DV" else "disabled"
        for w in self.dv_widgets:
            w.configure(state="readonly" if state == "normal" and isinstance(
                w, ttk.Combobox) else state)

    def _ok(self) -> None:
        try:
            bank_txt = self.v_bank.get()
            m = IcomMemory(
                number=self.mem.number, empty=False,
                freq=parse_mhz(self.v_freq.get()),
                offset=parse_mhz(self.v_off.get() or "0"),
                duplex={v: k for k, v in DUPLEX.items()}[self.v_dup.get()],
                mode=self.mode_names[self.v_mode.get()],
                name=self.v_name.get().rstrip(),
                tmode=self.tmode_vals[self.v_tmode.get()],
                rtone=TONES.index(float(self.v_rtone.get())),
                ctone=TONES.index(float(self.v_ctone.get())),
                dtcs=DTCS_CODES.index(int(self.v_dtcs.get())),
                dtcs_pol={v: k for k, v in
                          DTCS_POLARITY.items()}[self.v_pol.get()],
                step=self.step_vals[self.v_step.get()],
                skip={v: k for k, v in SKIPS.items()}[self.v_skip.get()],
                bank=None if bank_txt == "—" else ord(bank_txt[0]) - 65,
                bank_index=int(self.v_bidx.get() or 0),
                urcall=self.v_ur.get().upper().strip(),
                rpt1=self.v_r1.get().upper().rstrip(),
                rpt2=self.v_r2.get().upper().rstrip(),
                dv_code=int(self.v_code.get() or 0),
                dsql=self.dsql_vals[self.v_dsql.get()] if self.v_dsql
                else self.mem.dsql,
            )
            self.model.validate(m)
        except ValueError as e:
            messagebox.showerror("Valor inválido", str(e), parent=self)
            return
        self.result = m
        self.destroy()


# ============================================================== editor

class IcomEditor(tk.Toplevel):
    COLS = [("ch", "Canal", 52), ("name", "Nome", 120), ("freq", "MHz", 90),
            ("dup", "Dup", 40), ("off", "Offset", 65), ("mode", "Modo", 50),
            ("tmode", "Tom", 60), ("tone", "Tom Hz", 60),
            ("dtcs", "DTCS", 50), ("step", "Passo", 50), ("skip", "Skip", 55),
            ("bank", "Banco", 50), ("ur", "UR", 80), ("r1", "RPT1", 80),
            ("r2", "RPT2", 80)]

    def __init__(self, master, model: IcomModel):
        super().__init__(master)
        self.model = model
        self.geometry("1240x700")
        self.minsize(900, 500)
        self.image: bytearray = model.blank_image()
        self.image_source: str | None = None     # "radio" | "arquivo"
        self.meta = dict(model.icf_meta)
        self.path: str | None = None
        self.modified = False
        self.dirty: set[int] = set()
        self.clipboard: list[IcomMemory] = []
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_ev = threading.Event()
        self.sim = None
        self._build()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self._poll)
        self._log("INFO", f"{model.name}: {model.num_memories} memórias, "
                  f"imagem de {model.memsize} bytes")

    # ------------------------------------------------------------ layout
    def _build(self) -> None:
        mb = tk.Menu(self)
        m = tk.Menu(mb, tearoff=False)
        m.add_command(label="Abrir imagem (.icf)...", command=self.open_file,
                      accelerator="Ctrl+O")
        m.add_command(label="Salvar", command=self.save_file,
                      accelerator="Ctrl+S")
        m.add_command(label="Salvar como (.icf)...", command=self.save_as)
        m.add_separator()
        m.add_command(label="Exportar memórias (CSV)...",
                      command=self.export_csv)
        m.add_separator()
        m.add_command(label="Fechar", command=self.on_close)
        mb.add_cascade(label="Arquivo", menu=m)
        r = tk.Menu(mb, tearoff=False)
        r.add_command(label="Clonar do rádio (ler)", command=self.download)
        r.add_command(label="Clonar para o rádio (gravar)",
                      command=self.upload)
        mb.add_cascade(label="Rádio", menu=r)
        self.config(menu=mb)
        self.bind("<Control-o>", lambda e: self.open_file())
        self.bind("<Control-s>", lambda e: self.save_file())

        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        ttk.Label(tb, text="Porta:").pack(side="left")
        self.v_port = tk.StringVar()
        self.cb_port = ttk.Combobox(tb, textvariable=self.v_port, width=16)
        self.cb_port.pack(side="left", padx=(4, 2))
        ttk.Button(tb, text="↻", width=3, command=self.refresh_ports).pack(
            side="left")
        self.v_hispeed = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb, text="Alta velocidade (38400)",
                        variable=self.v_hispeed).pack(side="left", padx=8)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y",
                                                  padx=8)
        self.btn_dl = ttk.Button(tb, text="⬇ Clonar do rádio",
                                 command=self.download)
        self.btn_dl.pack(side="left")
        self.btn_ul = ttk.Button(tb, text="⬆ Clonar para o rádio",
                                 command=self.upload)
        self.btn_ul.pack(side="left", padx=4)
        ttk.Label(tb, text="Coloque o rádio em modo de clonagem antes de "
                  "clonar.", foreground="gray").pack(side="left", padx=10)
        self.refresh_ports()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8)

        fm = ttk.Frame(self.nb, padding=4)
        self.nb.add(fm, text="Memórias")
        bar = ttk.Frame(fm)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("Editar...", self.edit), ("Apagar", self.delete),
                          ("Copiar", self.copy), ("Colar", self.paste)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.v_show_empty = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Mostrar vazios", variable=self.v_show_empty,
                        command=self.refresh).pack(side="right")
        self.v_filter = tk.StringVar()
        ttk.Entry(bar, textvariable=self.v_filter, width=18).pack(
            side="right", padx=4)
        ttk.Label(bar, text="Filtro:").pack(side="right")
        self.v_filter.trace_add("write", lambda *a: self.refresh())

        tvf = ttk.Frame(fm)
        tvf.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(tvf, columns=[c[0] for c in self.COLS],
                               show="headings", selectmode="extended")
        for cid, title, w in self.COLS:
            self.tv.heading(cid, text=title)
            self.tv.column(cid, width=w, anchor="w", stretch=cid == "name")
        sb = ttk.Scrollbar(tvf, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.tag_configure("empty", foreground="#999999")
        self.tv.tag_configure("dirty", background="#fff3b0")
        self.tv.bind("<Double-1>", lambda e: self.edit())
        self.tv.bind("<Return>", lambda e: self.edit())
        self.tv.bind("<Delete>", lambda e: self.delete())
        self.tv.bind("<Control-c>", lambda e: self.copy())
        self.tv.bind("<Control-v>", lambda e: self.paste())

        fb = ttk.Frame(self.nb, padding=8)
        self.nb.add(fb, text="Bancos")
        ttk.Label(fb, text=f"Nomes dos bancos (até {self.model.bank_name_len}"
                  " caracteres):").grid(row=0, column=0, columnspan=6,
                                        sticky="w", pady=(0, 6))
        self.bank_vars: list[tk.StringVar] = []
        for i in range(self.model.num_banks):
            var = tk.StringVar()
            r, c = divmod(i, 3)
            ttk.Label(fb, text=chr(65 + i)).grid(row=r + 1, column=c * 2,
                                                 sticky="e", padx=(12, 4),
                                                 pady=2)
            e = ttk.Entry(fb, textvariable=var, width=20)
            e.grid(row=r + 1, column=c * 2 + 1, sticky="w", pady=2)
            e.bind("<FocusOut>", lambda ev, i=i: self._bank_changed(i))
            e.bind("<Return>", lambda ev, i=i: self._bank_changed(i))
            self.bank_vars.append(var)

        fl = ttk.Frame(self.nb, padding=4)
        self.nb.add(fl, text="Log")
        self.txt_log = tk.Text(fl, height=10, font=("TkFixedFont", 9))
        self.txt_log.pack(fill="both", expand=True)

        sf = ttk.Frame(self, padding=(8, 4))
        sf.pack(fill="x")
        self.v_status = tk.StringVar(value="Imagem vazia — clone do rádio "
                                     "ou abra um arquivo .icf")
        ttk.Label(sf, textvariable=self.v_status).pack(side="left")
        self.btn_cancel = ttk.Button(sf, text="Cancelar", state="disabled",
                                     command=self.cancel_ev.set)
        self.btn_cancel.pack(side="right")
        self.pb = ttk.Progressbar(sf, length=260)
        self.pb.pack(side="right", padx=8)

    # ------------------------------------------------------------- views
    def _title(self) -> None:
        name = os.path.basename(self.path) if self.path else "sem título"
        self.title(f"{'*' if self.modified else ''}{name} — "
                   f"Editor Icom {self.model.name}")

    def _set_modified(self) -> None:
        self.modified = True
        self._title()

    def _bank_names(self) -> list[str]:
        return [self.model.bank_name(self.image, i)
                for i in range(self.model.num_banks)]

    def _values(self, m: IcomMemory) -> list[str]:
        if m.empty:
            return [f"{m.number:03d}"] + [""] * (len(self.COLS) - 1)
        md = self.model
        dv = md.modes.get(m.mode) == "DV"
        tm = TONE_SHORT.get(m.tmode, "")
        tone = ""
        if tm == "Tone":
            tone = f"{TONES[m.rtone]:.1f}"
        elif tm.startswith("TSQL"):
            tone = f"{TONES[m.ctone]:.1f}"
        step = md.steps[m.step] if m.step < len(md.steps) else None
        return [
            f"{m.number:03d}", m.name, mhz(m.freq),
            DUPLEX[m.duplex] if m.duplex else "",
            f"{m.offset / 1e6:g}" if m.offset else "",
            md.modes.get(m.mode, "?"), tm, tone,
            f"{DTCS_CODES[m.dtcs]:03d}" if tm.startswith("DTCS") else "",
            f"{step:g}" if step else "?", SKIPS[m.skip] if m.skip else "",
            bank_label(m.bank) + (f"{m.bank_index:02d}" if m.bank is not None
                                  else ""),
            m.urcall if dv else "", m.rpt1 if dv else "",
            m.rpt2 if dv else "",
        ]

    def refresh(self) -> None:
        sel = set(self.tv.selection())
        self.tv.delete(*self.tv.get_children())
        flt = self.v_filter.get().strip().lower()
        used = 0
        for n in range(self.model.num_memories):
            m = self.model.decode(self.image, n)
            used += not m.empty
            if m.empty and not self.v_show_empty.get() and n not in self.dirty:
                continue
            vals = self._values(m)
            if flt and not any(flt in str(v).lower() for v in vals):
                continue
            tags = (("dirty",) if n in self.dirty else ()) + \
                (("empty",) if m.empty else ())
            self.tv.insert("", "end", iid=str(n), values=vals, tags=tags)
        keep = [i for i in sel if self.tv.exists(i)]
        if keep:
            self.tv.selection_set(keep)
        self.nb.tab(0, text=f"Memórias ({used}/{self.model.num_memories})")
        for i, var in enumerate(self.bank_vars):
            var.set(self.model.bank_name(self.image, i))
        self._title()

    def _log(self, direction: str, text: str) -> None:
        arrow = {"TX": "→", "RX": "←"}.get(direction, "•")
        self.txt_log.insert("end", f"{arrow} {text}\n")
        self.txt_log.see("end")

    # ----------------------------------------------------------- ações
    def _selected(self) -> list[int]:
        return sorted(int(i) for i in self.tv.selection())

    def edit(self) -> None:
        nums = self._selected()
        if not nums and not self.v_show_empty.get():
            # sem seleção: primeiro canal livre
            for n in range(self.model.num_memories):
                if self.model.decode(self.image, n).empty:
                    nums = [n]
                    break
        if not nums:
            return
        dlg = IcomMemoryDialog(self, self.model,
                               self.model.decode(self.image, nums[0]),
                               self._bank_names())
        self.wait_window(dlg)
        if dlg.result:
            self.model.encode(self.image, dlg.result)
            self.dirty.add(nums[0])
            self._set_modified()
            self.refresh()
            if self.tv.exists(str(nums[0])):
                self.tv.selection_set(str(nums[0]))
                self.tv.see(str(nums[0]))

    def delete(self) -> None:
        nums = [n for n in self._selected()
                if not self.model.decode(self.image, n).empty]
        if not nums or not messagebox.askyesno(
                "Apagar", f"Apagar {len(nums)} canal(is)?", parent=self):
            return
        for n in nums:
            self.model.encode(self.image, IcomMemory(number=n))
            self.dirty.add(n)
        self._set_modified()
        self.refresh()

    def copy(self) -> None:
        self.clipboard = [self.model.decode(self.image, n)
                          for n in self._selected()]
        self.v_status.set(f"{len(self.clipboard)} canal(is) copiado(s)")

    def paste(self) -> None:
        nums = self._selected()
        if not self.clipboard or not nums:
            return
        start = nums[0]
        if start + len(self.clipboard) > self.model.num_memories:
            messagebox.showerror("Colar", "Não cabe a partir deste canal.",
                                 parent=self)
            return
        try:
            for i, m in enumerate(self.clipboard):
                self.model.encode(self.image, m.copy_to(start + i))
                self.dirty.add(start + i)
        except ValueError as e:
            messagebox.showerror("Colar", str(e), parent=self)
        self._set_modified()
        self.refresh()

    def _bank_changed(self, i: int) -> None:
        name = self.bank_vars[i].get()
        if name != self.model.bank_name(self.image, i):
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                messagebox.showerror("Banco", "Use apenas caracteres ASCII.",
                                     parent=self)
                return
            self.model.set_bank_name(self.image, i, name)
            self._set_modified()

    # -------------------------------------------------------- arquivos
    def open_file(self) -> None:
        if self.modified and not messagebox.askyesno(
                "Abrir", "Descartar as alterações atuais?", parent=self):
            return
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("Imagem Icom", "*.icf"),
                                    ("Todos", "*.*")])
        if not path:
            return
        try:
            model_id, meta, img = read_icf(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("Abrir", f"Arquivo inválido: {e}",
                                 parent=self)
            return
        if model_id != self.model.model_id:
            other = model_for_id(model_id)
            messagebox.showerror(
                "Abrir", "Este arquivo é de outro rádio: "
                f"{other.name if other else model_id.hex(' ')}.",
                parent=self)
            return
        if len(img) != self.model.memsize:
            messagebox.showerror("Abrir", f"Tamanho inesperado: {len(img)} "
                                 f"bytes (esperado {self.model.memsize}).",
                                 parent=self)
            return
        self.image, self.meta, self.path = img, {**self.model.icf_meta,
                                                 **meta}, path
        self.image_source = "arquivo"
        self.modified = False
        self.dirty.clear()
        self.refresh()
        self.v_status.set(f"Aberto {path}")

    def save_file(self) -> bool:
        if not self.path:
            return self.save_as()
        try:
            write_icf(self.path, self.model.model_id, self.meta, self.image,
                      self.meta.get("recordsize", self.model.icf_recordsize))
        except OSError as e:
            messagebox.showerror("Salvar", str(e), parent=self)
            return False
        self.modified = False
        self._title()
        self.v_status.set(f"Salvo em {self.path}")
        return True

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".icf",
            filetypes=[("Imagem Icom", "*.icf")])
        if not path:
            return False
        self.path = path
        return self.save_file()

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(parent=self,
                                            defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([c[1] for c in self.COLS])
            for n in range(self.model.num_memories):
                m = self.model.decode(self.image, n)
                if not m.empty:
                    w.writerow(self._values(m))
        self.v_status.set(f"Exportado para {path}")

    # ------------------------------------------------------- clonagem
    def refresh_ports(self) -> None:
        ports = list_ports()
        self.cb_port["values"] = ports
        if self.v_port.get() not in ports:
            self.v_port.set(ports[0])

    def _open_port(self):
        port = self.v_port.get().strip()
        if port == SIMULATOR_PORT:
            if self.sim is None:
                from .simulator import SimulatedIcom
                self.sim = SimulatedIcom(self.model)
            self.sim.baudrate = 9600
            return self.sim
        import serial
        return serial.Serial(port, 9600, timeout=0.05)

    def _run(self, func, done) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            ser = self._open_port()
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("Porta serial", str(e), parent=self)
            return
        self.cancel_ev.clear()
        self.btn_cancel.configure(state="normal")
        for b in (self.btn_dl, self.btn_ul):
            b.configure(state="disabled")

        def progress(cur, total, text):
            self.q.put(("progress", cur, total, text))

        def log(d, t):
            self.q.put(("log", d, t))

        def target():
            try:
                result = func(ser, progress, log)
                self.q.put(("done", done, result, None))
            except Exception as e:  # noqa: BLE001
                self.q.put(("done", done, None, e))
            finally:
                if ser is not self.sim:
                    ser.close()

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _poll(self) -> None:
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    _, cur, total, text = msg
                    self.pb["maximum"] = max(total, 1)
                    self.pb["value"] = cur
                    self.v_status.set(text)
                elif msg[0] == "log":
                    self._log(msg[1], msg[2])
                elif msg[0] == "done":
                    _, done, result, error = msg
                    self.btn_cancel.configure(state="disabled")
                    for b in (self.btn_dl, self.btn_ul):
                        b.configure(state="normal")
                    if error is not None:
                        self.v_status.set(f"Erro: {error}")
                        self._log("ERRO", str(error))
                        if not isinstance(error, C.CloneCancelled):
                            messagebox.showerror("Clonagem", str(error),
                                                 parent=self)
                    else:
                        done(result)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def download(self) -> None:
        if self.modified and not messagebox.askyesno(
                "Clonar do rádio", "Descartar as alterações atuais?",
                parent=self):
            return
        hispeed = self.v_hispeed.get()

        def task(ser, progress, log):
            return C.clone_from_radio(ser, self.model, progress,
                                      self.cancel_ev, hispeed, log)

        def done(img):
            self.image = img
            self.image_source = "radio"
            self.meta = dict(self.model.icf_meta)
            self.path = None
            self.modified = True
            self.dirty.clear()
            self.refresh()
            self.v_status.set("Clonagem do rádio concluída — salve um "
                              "backup (.icf)")

        self._run(task, done)

    def upload(self) -> None:
        if self.image_source is None:
            messagebox.showwarning(
                "Clonar para o rádio",
                "Por segurança, primeiro clone do rádio ou abra um arquivo "
                ".icf deste modelo. A clonagem substitui TODA a memória do "
                "rádio (inclusive configurações), e uma imagem vazia apagaria "
                "tudo.", parent=self)
            return
        if not messagebox.askyesno(
                "Clonar para o rádio",
                f"Gravar a imagem inteira no {self.model.name}?\n\n"
                "O rádio precisa estar em modo de clonagem e não deve ser "
                "desligado durante a gravação.", parent=self):
            return
        hispeed = self.v_hispeed.get()
        image = bytes(self.image)
        map_rev = int(self.meta.get("MapRev", 1))

        def task(ser, progress, log):
            C.clone_to_radio(ser, self.model, image, progress,
                             self.cancel_ev, hispeed, log, map_rev)

        def done(_):
            self.dirty.clear()
            self.refresh()
            self.v_status.set("Clonagem para o rádio concluída")

        self._run(task, done)

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Fechar", "Aguarde o fim da clonagem.",
                                   parent=self)
            return
        if self.modified:
            ans = messagebox.askyesnocancel(
                "Fechar", "Salvar a imagem antes de fechar?", parent=self)
            if ans is None or (ans and not self.save_file()):
                return
        self.destroy()
