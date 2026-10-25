"""Torna o tkinter tolerante ao coletor de lixo em threads de trabalho.

Janelas e diálogos fechados formam ciclos de referência; se o GC do Python
os coletar numa thread de comunicação serial, `Variable.__del__` tenta falar
com o Tcl fora do thread principal e gera "main thread is not in main loop".
Fora do thread principal, a remoção da variável Tcl é simplesmente pulada
(o vazamento é de alguns bytes por variável).
"""

import threading
import tkinter as tk

_original_del = tk.Variable.__del__


def _safe_del(self):
    if threading.current_thread() is threading.main_thread():
        _original_del(self)


tk.Variable.__del__ = _safe_del
