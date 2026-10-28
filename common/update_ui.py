"""Janelas da atualização automática."""

from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import updater as U


def check_async(master: tk.Misc, manual: bool) -> None:
    """Consulta o site em segundo plano e mostra o resultado."""
    q: queue.Queue = queue.Queue()

    def work():
        try:
            q.put(("ok", U.check()))
        except U.UpdateError as e:
            q.put(("erro", str(e)))

    threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            kind, value = q.get_nowait()
        except queue.Empty:
            master.after(200, poll)
            return
        cfg = U.load_config()
        cfg["last_check"] = time.time()
        U.save_config(cfg)
        if kind == "erro":
            if manual:
                messagebox.showwarning("Atualização", value, parent=master)
            return
        info: U.UpdateInfo = value
        newer = U.is_newer(info.version, U.current_version())
        if not newer:
            if manual:
                messagebox.showinfo(
                    "Atualização", f"Você já tem a versão mais recente "
                    f"({U.current_version()}).", parent=master)
            return
        if not manual and cfg.get("skip_version") == info.version:
            return
        UpdateDialog(master, info)

    master.after(200, poll)


class UpdateDialog(tk.Toplevel):
    def __init__(self, master, info: U.UpdateInfo):
        super().__init__(master)
        self.info = info
        self.kind = U.install_kind()
        self.entry = info.files.get(self.kind)
        self.cancel_ev = threading.Event()
        self.q: queue.Queue = queue.Queue()
        self.title("Nova versão disponível")
        self.transient(master)
        self.resizable(False, False)
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"PT2VHF Prog Tool {info.version}",
                  font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Você usa a versão {U.current_version()}"
                  + (f" · publicada em {info.date}" if info.date else ""),
                  foreground="gray").pack(anchor="w", pady=(0, 8))
        if info.notes:
            ttk.Label(f, text="Novidades:").pack(anchor="w")
            ttk.Label(f, text="\n".join(f"• {n}" for n in info.notes),
                      wraplength=420, justify="left").pack(anchor="w",
                                                           pady=(0, 8))
        self.v_status = tk.StringVar(value=self._hint())
        ttk.Label(f, textvariable=self.v_status, wraplength=420,
                  justify="left").pack(anchor="w")
        self.pb = ttk.Progressbar(f, length=420)
        self.pb.pack(fill="x", pady=8)
        b = ttk.Frame(f)
        b.pack(fill="x")
        self.btn_go = ttk.Button(
            b, text="Atualizar agora" if self.kind == "windows-instalador"
            else "Baixar", command=self.start)
        self.btn_go.pack(side="right")
        ttk.Button(b, text="Lembrar depois", command=self.close).pack(
            side="right", padx=6)
        ttk.Button(b, text="Pular esta versão", command=self.skip).pack(
            side="left")
        if self.entry is None:
            self.btn_go.configure(text="Abrir o site", command=self.open_page)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _hint(self) -> str:
        return {
            "windows-instalador": "O instalador será baixado, conferido e "
            "executado; o programa fecha e reabre já atualizado.",
            "windows-portatil": "O novo .zip será baixado para a pasta "
            "Downloads; descompacte-o no lugar da pasta atual.",
            "deb": "O novo pacote .deb será baixado e aberto no instalador "
            "de programas do sistema.",
            "tgz": "O novo .tar.gz será baixado para a pasta Downloads.",
        }.get(self.kind, "")

    def open_page(self) -> None:
        import webbrowser
        webbrowser.open(self.info.page)
        self.close()

    def skip(self) -> None:
        cfg = U.load_config()
        cfg["skip_version"] = self.info.version
        U.save_config(cfg)
        self.close()

    def close(self) -> None:
        self.cancel_ev.set()
        self.destroy()

    def start(self) -> None:
        if self.kind == "windows-instalador" and not messagebox.askyesno(
                "Atualizar", "O programa será fechado para instalar a nova "
                "versão. Salve antes os projetos abertos.\n\nContinuar?",
                parent=self):
            return
        self.btn_go.configure(state="disabled")
        self.v_status.set("Baixando...")
        entry = self.entry
        dest = U.downloads_dir() if self.kind != "windows-instalador" \
            else os.path.join(os.environ.get("TEMP", U.downloads_dir()))

        def work():
            try:
                path = U.download(entry, dest,
                                  lambda d, t: self.q.put(("prog", d, t)),
                                  self.cancel_ev)
                self.q.put(("ok", path))
            except U.UpdateError as e:
                self.q.put(("erro", str(e)))

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "prog":
                    self.pb["maximum"] = max(msg[2], 1)
                    self.pb["value"] = msg[1]
                    if msg[2]:
                        self.v_status.set(f"Baixando... {msg[1] * 100 // msg[2]}%")
                elif msg[0] == "erro":
                    self.v_status.set(msg[1])
                    self.btn_go.configure(state="normal")
                    return
                else:
                    self._finish(msg[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, path: str) -> None:
        if self.kind == "windows-instalador":
            self.v_status.set("Instalando a nova versão...")
            self.update()
            U.launch_installer(path)
            os._exit(0)     # libera os arquivos para o instalador
        self.v_status.set(f"Arquivo conferido e salvo em:\n{path}")
        self.btn_go.configure(text="Abrir", state="normal",
                              command=lambda: (U.open_path(path),
                                               self.close()))
