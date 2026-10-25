"""Constantes visuais compartilhadas."""

import sys

# "Helvetica" é apelido no Tk do Linux/macOS; no Windows usa-se Arial, que
# existe em todas as versões.
UI_FONT = "Arial" if sys.platform == "win32" else "Helvetica"
