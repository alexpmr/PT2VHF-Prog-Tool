"""Janelas da atualização automática."""

from __future__ import annotations

import os
import queue
import tempfile
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
        self.btn_go = ttk.Button(b, text="Atualizar agora",
                                 command=self.start)
        self.btn_go.pack(side="right")
        ttk.Button(b, text="Lembrar depois", command=self.close).pack(
            side="right", padx=6)
        ttk.Button(b, text="Pular esta versão", command=self.skip).pack(
            side="left")
        if self.entry is None:
            self.btn_go.configure(text="Abrir o site",
                                  command=self.open_page)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _hint(self) -> str:
        return {
            "windows-instalador": "O instalador será baixado, conferido e "
            "executado; o programa fecha e reabre já atualizado.",
            "windows-portatil": "A nova versão será baixada, conferida e "
            "copiada sobre a pasta atual; o programa reabre atualizado.",
            "deb": "O novo pacote .deb será baixado, conferido e instalado "
            "(o sistema pede a senha de administrador).",
            "tgz": "A nova versão será baixada, conferida e copiada sobre a "
            "pasta atual; o programa reabre atualizado.",
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
        if not messagebox.askyesno(
                "Atualizar", "O programa será fechado para instalar a nova "
                "versão. Salve antes os projetos abertos.\n\nContinuar?",
                parent=self):
            return
        self.btn_go.configure(state="disabled")
        self.v_status.set("Baixando...")
        entry = self.entry
        dest = U.downloads_dir() if self.kind == "deb" \
            else tempfile.mkdtemp(prefix="pt2vhf-dl-")

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
        self.v_status.set("Arquivo conferido. Instalando...")
        self.update()
        try:
            action = U.apply_update(path, self.kind)
        except U.UpdateError as e:
            self.v_status.set(str(e))
            self.btn_go.configure(state="normal")
            return
        if action == "exit":
            os._exit(0)     # o instalador/script reabre o programa
        if action == "restart":
            messagebox.showinfo("Atualização",
                                f"Versão {self.info.version} instalada. "
                                "O programa será reaberto.", parent=self)
            U.restart()
        self.v_status.set(f"Arquivo conferido e salvo em:\n{path}\n"
                          "Conclua a instalação por ele.")
        self.btn_go.configure(text="Fechar", state="normal",
                              command=self.close)


class VersionDialog(tk.Toplevel):
    """Compara a versão instalada com a publicada no site."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Versões — PT2VHF Prog Tool")
        self.transient(master)
        self.resizable(False, False)
        self.info: U.UpdateInfo | None = None
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        cfg = U.load_config()
        last = cfg.get("last_check")
        rows = [
            ("Versão instalada", U.current_version()),
            ("Tipo de instalação", U.KIND_LABELS.get(U.install_kind(), "?")),
            ("Pasta", U.app_dir()),
            ("Site de atualização", U.update_url()),
            ("Última verificação", time.strftime(
                "%d/%m/%Y %H:%M", time.localtime(last)) if last else "nunca"),
        ]
        for i, (k, v) in enumerate(rows):
            ttk.Label(f, text=k + ":", foreground="gray").grid(
                row=i, column=0, sticky="nw", padx=(0, 10), pady=2)
            ttk.Label(f, text=v, wraplength=380).grid(row=i, column=1,
                                                     sticky="w", pady=2)
        ttk.Separator(f).grid(row=len(rows), columnspan=2, sticky="we",
                              pady=8)
        self.v_site = tk.StringVar(value="Consultando o site...")
        ttk.Label(f, text="Versão no site:", foreground="gray").grid(
            row=len(rows) + 1, column=0, sticky="nw", padx=(0, 10))
        ttk.Label(f, textvariable=self.v_site, wraplength=380,
                  justify="left").grid(row=len(rows) + 1, column=1,
                                       sticky="w")
        self.v_auto = tk.BooleanVar(value=cfg.get("auto_update", True))
        ttk.Checkbutton(f, text="Verificar automaticamente todo dia",
                        variable=self.v_auto, command=self._toggle).grid(
            row=len(rows) + 2, columnspan=2, sticky="w", pady=(10, 0))
        b = ttk.Frame(f)
        b.grid(row=len(rows) + 3, columnspan=2, sticky="e", pady=(12, 0))
        self.btn_update = ttk.Button(b, text="Atualizar agora",
                                     state="disabled", command=self._update)
        self.btn_update.pack(side="right")
        ttk.Button(b, text="Verificar de novo",
                   command=self._check).pack(side="right", padx=6)
        ttk.Button(b, text="Fechar", command=self.destroy).pack(side="right")
        self._check()

    def _toggle(self) -> None:
        cfg = U.load_config()
        cfg["auto_update"] = self.v_auto.get()
        U.save_config(cfg)

    def _check(self) -> None:
        self.v_site.set("Consultando o site...")
        self.btn_update.configure(state="disabled")
        q: queue.Queue = queue.Queue()

        def work():
            try:
                q.put(("ok", U.check()))
            except U.UpdateError as e:
                q.put(("erro", str(e)))

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not self.winfo_exists():
                return
            try:
                kind, value = q.get_nowait()
            except queue.Empty:
                self.after(200, poll)
                return
            cfg = U.load_config()
            cfg["last_check"] = time.time()
            U.save_config(cfg)
            if kind == "erro":
                self.v_site.set(f"Não foi possível verificar: {value}")
                return
            self.info = value
            cur = U.current_version()
            date = f" (publicada em {value.date})" if value.date else ""
            if U.is_newer(value.version, cur):
                self.v_site.set(f"{value.version}{date} — nova versão "
                                "disponível")
                self.btn_update.configure(state="normal")
            elif U.is_newer(cur, value.version):
                self.v_site.set(f"{value.version}{date} — a instalada é "
                                "mais nova que a do site")
            else:
                self.v_site.set(f"{value.version}{date} — você está "
                                "atualizado")

        self.after(200, poll)

    def _update(self) -> None:
        if self.info:
            master = self.master
            self.destroy()
            UpdateDialog(master, self.info)
