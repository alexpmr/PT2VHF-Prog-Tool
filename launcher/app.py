"""Tela inicial: escolha do fabricante e do rádio."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from common.ui import UI_FONT

from .art import Picture, find_asset

BG = "#eef1f5"
CARD = "#ffffff"
CARD_HOVER = "#dde9f7"
TEXT = "#1d2433"
MUTED = "#5d6678"


# Fabricantes e rádios da tela inicial. Para incluir um rádio, acrescente
# (chave, modelo, descrição, tamanho da figura) na lista do fabricante e
# trate a chave em Launcher.open_radio.
BRANDS = {
    "kenwood": ("Kenwood", "Transceptores HF/VHF/UHF", [
        ("ts2000", "TS-2000",
         "Memórias, menus e display em tempo real (CAT serial)", (260, 130)),
    ]),
    "icom": ("ICOM", "Portáteis e móveis D-STAR", [
        ("id51plus2", "ID-51A Plus2",
         "Portátil D-STAR VHF/UHF — 500 memórias", (200, 150)),
        ("id880h", "ID-880H", "Móvel D-STAR VHF/UHF — 1000 memórias",
         (200, 150)),
    ]),
}


class Card(tk.Frame):
    """Botão grande com imagem, título e descrição."""

    def __init__(self, master, picture: str, title: str, subtitle: str,
                 command, pic_size=(240, 120)):
        super().__init__(master, bg=CARD, cursor="hand2", padx=14, pady=12,
                         highlightthickness=1, highlightbackground="#cfd6e0")
        self.command = command
        self.pic = Picture(self, picture, *pic_size, bg=CARD)
        self.pic.pack()
        self.lbl = tk.Label(self, text=title, bg=CARD, fg=TEXT,
                            font=(UI_FONT, 14, "bold"))
        self.lbl.pack(pady=(8, 0))
        self.sub = tk.Label(self, text=subtitle, bg=CARD, fg=MUTED,
                            font=(UI_FONT, 10), wraplength=pic_size[0])
        self.sub.pack()
        for w in (self, self.pic, self.lbl, self.sub):
            w.bind("<Button-1>", lambda e: self.command())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        self.configure(takefocus=1)
        self.bind("<Return>", lambda e: self.command())
        self.bind("<space>", lambda e: self.command())

    def _hover(self, on: bool) -> None:
        color = CARD_HOVER if on else CARD
        for w in (self, self.pic, self.lbl, self.sub):
            w.configure(bg=color)


class Launcher(tk.Tk):
    def __init__(self):
        # className define o WM_CLASS no Linux (casa com o .desktop)
        super().__init__(className="pt2vhf-prog-tool")
        self.title("PT2VHF Prog Tool")
        self.geometry("820x520")
        self.minsize(640, 440)
        self.configure(bg=BG)
        self._set_icon()
        self.windows: dict[str, tk.Toplevel] = {}
        self.page: tk.Frame | None = None
        self._build_footer()
        self.show_home()
        # Aviso do site oficial a cada abertura; a verificação de versão nova
        # só roda quando ele é fechado, para os avisos virem em sequência.
        self.after(300, self.show_site_notice)

    def _build_footer(self) -> None:
        from . import __version__
        from common import updater
        foot = tk.Frame(self, bg=BG)
        foot.pack(side="bottom", fill="x", padx=24, pady=(0, 10))
        tk.Label(foot, text=f"Versão {__version__}", bg=BG, fg=MUTED,
                 font=(UI_FONT, 9)).pack(side="left")
        link = tk.Label(foot, text="Versões e atualizações", bg=BG,
                        fg="#1d4f91", cursor="hand2",
                        font=(UI_FONT, 9, "underline"))
        link.pack(side="left", padx=12)
        link.bind("<Button-1>", lambda e: self.show_versions())
        self.v_auto = tk.BooleanVar(
            value=updater.load_config().get("auto_update", True))
        tk.Checkbutton(foot, text="Verificar automaticamente",
                       variable=self.v_auto, bg=BG, fg=MUTED,
                       activebackground=BG, highlightthickness=0,
                       font=(UI_FONT, 9),
                       command=self._toggle_auto).pack(side="left")

    def _toggle_auto(self) -> None:
        from common import updater
        cfg = updater.load_config()
        cfg["auto_update"] = self.v_auto.get()
        updater.save_config(cfg)

    def show_site_notice(self) -> None:
        from common.update_ui import SiteNoticeDialog
        SiteNoticeDialog(self, on_close=self._auto_check)

    def _auto_check(self) -> None:
        from common import updater
        if updater.auto_check_due(updater.load_config()):
            self.check_updates(False)

    def show_versions(self) -> None:
        from common.update_ui import VersionDialog
        VersionDialog(self)

    def check_updates(self, manual: bool) -> None:
        from common.update_ui import check_async
        check_async(self, manual)

    def _set_icon(self) -> None:
        """Ícone de todas as janelas (.ico no Windows, PNG nos demais)."""
        try:
            if sys.platform == "win32":
                icon = find_asset("app.ico")
                if icon:
                    self.iconbitmap(default=icon)
            else:
                png = find_asset("app.png")
                if png:
                    self._icon = tk.PhotoImage(file=png)
                    self.iconphoto(True, self._icon)
        except tk.TclError:
            pass

    # ----------------------------------------------------------- páginas
    def _new_page(self, title: str, subtitle: str,
                  back: bool = False) -> tk.Frame:
        if self.page is not None:
            self.page.destroy()
        self.page = tk.Frame(self, bg=BG)
        self.page.pack(fill="both", expand=True, padx=24, pady=18)
        head = tk.Frame(self.page, bg=BG)
        head.pack(fill="x")
        if back:
            ttk.Button(head, text="← Voltar", command=self.show_home).pack(
                side="left", padx=(0, 12))
        box = tk.Frame(head, bg=BG)
        box.pack(side="left")
        tk.Label(box, text=title, bg=BG, fg=TEXT,
                 font=(UI_FONT, 20, "bold")).pack(anchor="w")
        tk.Label(box, text=subtitle, bg=BG, fg=MUTED,
                 font=(UI_FONT, 11)).pack(anchor="w")
        body = tk.Frame(self.page, bg=BG)
        body.pack(expand=True)
        return body

    def show_home(self) -> None:
        body = self._new_page("PT2VHF Prog Tool",
                              "Escolha o fabricante do rádio")
        for col, (key, (name, sub, _)) in enumerate(BRANDS.items()):
            Card(body, key, name, sub,
                 lambda k=key: self.show_brand(k)).grid(
                row=0, column=col, padx=16, pady=16)

    def show_brand(self, brand: str) -> None:
        name, _, radios = BRANDS[brand]
        body = self._new_page(name, "Escolha o rádio", back=True)
        for i, (key, model, sub, size) in enumerate(radios):
            r, c = divmod(i, 3)
            Card(body, key, model, sub, lambda k=key: self.open_radio(k),
                 pic_size=size).grid(row=r, column=c, padx=16, pady=16)

    # compatibilidade
    def show_kenwood(self) -> None:
        self.show_brand("kenwood")

    def show_icom(self) -> None:
        self.show_brand("icom")

    def open_radio(self, key: str) -> None:
        if key == "ts2000":
            self.open_ts2000()
        else:
            self.open_icom(key)

    # --------------------------------------------------------- editores
    def _open(self, key: str, factory) -> None:
        win = self.windows.get(key)
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus_force()
            return
        win = factory()
        self.windows[key] = win

    def open_ts2000(self) -> None:
        from ts2000prog.gui import App
        self._open("ts2000", lambda: App(self))

    def open_icom(self, key: str) -> None:
        from icomprog.gui import IcomEditor
        from icomprog.models import MODELS
        self._open(key, lambda: IcomEditor(self, MODELS[key]))


def main() -> None:
    Launcher().mainloop()


if __name__ == "__main__":
    main()
