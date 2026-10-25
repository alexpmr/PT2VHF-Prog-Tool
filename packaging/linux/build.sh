#!/usr/bin/env bash
# Gera os pacotes Linux a partir do commit atual:
#   dist/pt2vhf-prog-tool_<versão>_all.deb      (Debian, Ubuntu, Mint...)
#   dist/pt2vhf-prog-tool-<versão>-linux.tar.gz (qualquer distro; macOS)
#
# Requisitos: git, dpkg-deb. Uso: packaging/linux/build.sh (na raiz)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' launcher/__init__.py)
PKG=pt2vhf-prog-tool
MAINTAINER="${MAINTAINER:-alexpmr <alexpmr@gmail.com>}"
# arquivos do programa (sem testes, docs e empacotamento)
APP_FILES=$(git ls-files main.py launcher ts2000prog icomprog common assets)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p dist

# ------------------------------------------------------------------ .deb
D="$STAGE/deb"
LIB="$D/usr/lib/$PKG"
mkdir -p "$LIB" "$D/usr/bin" "$D/usr/share/applications" \
         "$D/usr/share/doc/$PKG" "$D/DEBIAN"
for f in $APP_FILES; do
  install -D -m 644 "$f" "$LIB/$f"
done

cat > "$D/usr/bin/$PKG" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/pt2vhf-prog-tool/main.py "$@"
EOF
chmod 755 "$D/usr/bin/$PKG"

cat > "$D/usr/share/applications/$PKG.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=PT2VHF Prog Tool
GenericName=Programador de rádios
Comment=Programação do Kenwood TS-2000 e dos Icom ID-51A Plus2 e ID-880H
Exec=pt2vhf-prog-tool
Icon=pt2vhf-prog-tool
Terminal=false
Categories=Network;HamRadio;
Keywords=rádio;radio;kenwood;icom;ts-2000;id-51;id-880;radioamador;
StartupWMClass=Pt2vhf-prog-tool
EOF

for n in 48 64 128 256; do
  install -D -m 644 "packaging/linux/icons/$n.png" \
    "$D/usr/share/icons/hicolor/${n}x${n}/apps/$PKG.png"
done

cat > "$D/usr/share/doc/$PKG/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: pt2vhf-prog-tool

Files: *
Copyright: 2026 alexpmr
License: GPL-3+
Comment: Os mapas de memória dos rádios Icom foram derivados dos drivers do
 CHIRP (https://chirpmyradio.com), licenciado sob GPLv3.
 On Debian systems, the full text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.
EOF
printf '%s (%s) stable; urgency=low\n\n  * Versão %s.\n\n -- %s  %s\n' \
  "$PKG" "$VERSION" "$VERSION" "$MAINTAINER" "$(date -R)" \
  | gzip -9n > "$D/usr/share/doc/$PKG/changelog.gz"

SIZE=$(du -sk --exclude=DEBIAN "$D" | cut -f1)
cat > "$D/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: hamradio
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-tk, python3-serial
Replaces: programador-radios
Conflicts: programador-radios
Installed-Size: $SIZE
Maintainer: $MAINTAINER
Description: programador para Kenwood TS-2000 e Icom ID-51A Plus2/ID-880H
 Edita memórias e menus do Kenwood TS-2000 pela porta serial (CAT), com
 display LCD em tempo real, e edita as memórias dos Icom ID-51A Plus2 e
 ID-880H por clonagem (arquivos .icf).
EOF

cat > "$D/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
  # restos da versão 1.1.0, que se chamava programador-radios
  if [ -d /usr/lib/programador-radios ] && \
     ! dpkg-query -W -f='${Status}' programador-radios 2>/dev/null \
       | grep -q "ok installed"; then
    rm -rf /usr/lib/programador-radios
  fi
  echo "PT2VHF Prog Tool: para usar a porta serial, seu usuário precisa"
  echo "estar no grupo 'dialout':  sudo usermod -aG dialout \$USER  (e entre"
  echo "de novo na sessão)."
fi
EOF
chmod 755 "$D/DEBIAN/postinst"

# caches .pyc criados em tempo de execução não pertencem ao pacote
cat > "$D/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
find /usr/lib/pt2vhf-prog-tool -type d -name __pycache__ -prune \
  -exec rm -rf {} + 2>/dev/null || true
EOF
chmod 755 "$D/DEBIAN/prerm"
find "$D" -type d -exec chmod 755 {} +
DEB="dist/${PKG}_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$D" "$DEB" >/dev/null
echo "Gerado: $DEB"

# --------------------------------------------------------------- .tar.gz
T="$STAGE/$PKG-$VERSION"
mkdir -p "$T"
for f in $APP_FILES README.md requirements.txt LICENSE; do
  install -D -m 644 "$f" "$T/$f"
done
cat > "$T/pt2vhf-prog-tool.sh" <<'EOF'
#!/bin/sh
# Inicia o PT2VHF Prog Tool. Requer Python 3.10+ com Tkinter e pyserial.
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if ! "$PY" -c "import tkinter" 2>/dev/null; then
  echo "Falta o Tkinter. Instale, por exemplo:"
  echo "  Debian/Ubuntu: sudo apt install python3-tk"
  echo "  Fedora:        sudo dnf install python3-tkinter"
  echo "  Arch:          sudo pacman -S tk"
  echo "  macOS:         instale o Python de https://www.python.org"
  exit 1
fi
if ! "$PY" -c "import serial" 2>/dev/null; then
  echo "Instalando pyserial para o seu usuário..."
  "$PY" -m pip install --user pyserial || {
    echo "Instale o pyserial: pacote python3-serial (Linux) ou 'pip install pyserial'"
    exit 1; }
fi
exec "$PY" main.py "$@"
EOF
chmod 755 "$T/pt2vhf-prog-tool.sh"
cat > "$T/LEIA-ME.txt" <<EOF
PT2VHF Prog Tool $VERSION — Linux (qualquer distribuição) e macOS

1. Instale o Python 3.10 ou mais novo com Tkinter (veja pt2vhf-prog-tool.sh).
2. Execute:  ./pt2vhf-prog-tool.sh
3. Linux: para acessar a porta serial, adicione seu usuário ao grupo
   dialout (sudo usermod -aG dialout \$USER) e entre de novo na sessão.

Em Debian, Ubuntu e Mint prefira o pacote .deb.
EOF
TGZ="dist/$PKG-$VERSION-linux.tar.gz"
tar -C "$STAGE" --owner=0 --group=0 -czf "$TGZ" "$PKG-$VERSION"
echo "Gerado: $TGZ"
