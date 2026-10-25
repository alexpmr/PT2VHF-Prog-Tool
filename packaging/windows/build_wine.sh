#!/usr/bin/env bash
# Gera o executável e o instalador Windows a partir do Linux, usando Wine.
#
# Pré-requisitos (Ubuntu/Debian):
#   sudo dpkg --add-architecture i386 && sudo apt update
#   sudo apt install wine64 wine32:i386 nsis xvfb
# Na primeira execução o script instala, dentro de um prefixo Wine próprio,
# o Miniconda para Windows (Python 3.12 com Tcl/Tk) e o PyInstaller.
#
# Uso: packaging/windows/build_wine.sh   (na raiz do projeto)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CACHE="${BUILD_CACHE:-$HOME/.cache/programador-radios-winbuild}"
export WINEPREFIX="$CACHE/wineprefix" WINEDEBUG=-all
export LANG=C.UTF-8 LC_ALL=C.UTF-8
MINICONDA="Miniconda3-py312_26.7.1-1-Windows-x86_64.exe"
mkdir -p "$CACHE/wheels"
cd "$ROOT"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' launcher/__init__.py)

if [ ! -f "$WINEPREFIX/drive_c/mc/python.exe" ]; then
  echo ">> Preparando Wine + Miniconda (uma vez só)"
  [ -f "$CACHE/$MINICONDA" ] || curl -fL -o "$CACHE/$MINICONDA" \
    "https://repo.anaconda.com/miniconda/$MINICONDA"
  xvfb-run -a wineboot -i
  xvfb-run -a wine "$CACHE/$MINICONDA" /InstallationType=JustMe \
    /RegisterPython=0 /AddToPath=0 /S '/D=C:\mc'
  pip download -q -d "$CACHE/wheels" --platform win_amd64 \
    --python-version 3.12 --only-binary=:all: "pyinstaller==6.11.1" pyserial
  pip download -q -d "$CACHE/wheels" --no-deps "pefile==2023.2.7" \
    "pywin32-ctypes==0.2.3"
  WH="Z:$(echo "$CACHE/wheels" | sed 's#/#\\#g')"
  wine 'C:\mc\python.exe' -m pip install --no-index --find-links "$WH" \
    "pyinstaller==6.11.1" pyserial </dev/null | cat
fi

echo ">> PyInstaller $VERSION"
rm -rf build/pyinstaller dist/ProgramadorRadios
# as DLLs do conda (Tcl/Tk, ffi, OpenSSL...) ficam em Library\bin
WINEPATH='C:\mc\Library\bin;C:\mc' wine 'C:\mc\python.exe' -m PyInstaller \
  --noconfirm --clean --distpath dist --workpath build/pyinstaller \
  packaging/windows/programador.spec </dev/null | cat

echo ">> NSIS"
makensis -V2 -DVERSION="$VERSION" packaging/windows/installer.nsi
echo ">> Versão portátil"
PORT="dist/ProgramadorRadios-$VERSION-windows-portatil.zip"
rm -rf "dist/Programador de Radios" "$PORT"
cp -r dist/ProgramadorRadios "dist/Programador de Radios"
cp LICENSE "dist/Programador de Radios/LICENCA.txt"
(cd dist && zip -qr "../$PORT" "Programador de Radios")
rm -rf "dist/Programador de Radios"
echo "Pronto: dist/ProgramadorRadios-$VERSION-instalador.exe e $PORT"
