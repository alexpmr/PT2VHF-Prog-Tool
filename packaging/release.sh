#!/usr/bin/env bash
# Gera todos os pacotes e a página de download (Linux + Wine).
#   packaging/release.sh   ->  dist/site/ e dist/site.zip
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain)" ]; then
  echo "Há alterações não commitadas; o zip do código-fonte usa o último commit." >&2
fi
python3 -m unittest discover -s tests
packaging/windows/build_wine.sh
packaging/linux/build.sh
python3 packaging/site/build_site.py
