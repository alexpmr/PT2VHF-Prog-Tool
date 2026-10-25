"""Tela inicial: escolha do fabricante e do rádio."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .art import Picture

BG = "#eef1f5"
CARD = "#ffffff"
CARD_HOVER = "#dde9f7"
TEXT = "#1d2433"
MUTED = "#5d6678"


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
                            font=("Helvetica", 14, "bold"))
        self.lbl.pack(pady=(8, 0))
        self.sub = tk.Label(self, text=subtitle, bg=CARD, fg=MUTED,
                            font=("Helvetica", 10), wraplength=pic_size[0])
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
        super().__init__()
        self.title("Programador de Rádios")
        self.geometry("820x520")
        self.minsize(640, 440)
        self.configure(bg=BG)
        self.windows: dict[str, tk.Toplevel] = {}
        self.page: tk.Frame | None = None
        self.show_home()

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
                 font=("Helvetica", 20, "bold")).pack(anchor="w")
        tk.Label(box, text=subtitle, bg=BG, fg=MUTED,
                 font=("Helvetica", 11)).pack(anchor="w")
        body = tk.Frame(self.page, bg=BG)
        body.pack(expand=True)
        return body

    def show_home(self) -> None:
        body = self._new_page("Programador de Rádios",
                              "Escolha o fabricante do rádio")
        Card(body, "kenwood", "Kenwood", "Transceptores HF/VHF/UHF",
             self.show_kenwood).grid(row=0, column=0, padx=16, pady=16)
        Card(body, "icom", "ICOM", "Portáteis e móveis D-STAR",
             self.show_icom).grid(row=0, column=1, padx=16, pady=16)

    def show_kenwood(self) -> None:
        body = self._new_page("Kenwood", "Rádios suportados", back=True)
        Card(body, "ts2000", "TS-2000",
             "Memórias, menus e display em tempo real (CAT serial)",
             self.open_ts2000, pic_size=(260, 130)).grid(row=0, column=0,
                                                         padx=16, pady=16)

    def show_icom(self) -> None:
        body = self._new_page("ICOM", "Rádios suportados", back=True)
        Card(body, "id51plus2", "ID-51A Plus2",
             "Portátil D-STAR VHF/UHF — 500 memórias",
             lambda: self.open_icom("id51plus2"),
             pic_size=(200, 150)).grid(row=0, column=0, padx=16, pady=16)
        Card(body, "id880h", "ID-880H",
             "Móvel D-STAR VHF/UHF — 1000 memórias",
             lambda: self.open_icom("id880h"),
             pic_size=(200, 150)).grid(row=0, column=1, padx=16, pady=16)

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
