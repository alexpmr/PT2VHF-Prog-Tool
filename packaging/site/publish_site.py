"""Publica a versão atual no repositório do site (PT2VHF-Site).

Segue o roteiro "Publicar uma nova versão de um programa" do README do site:
copia os pacotes de dist/site/ para downloads/prog-tool/ (apagando os da
versão anterior) e atualiza products.prog em updates.json, incluindo a
assinatura Ed25519 de cada arquivo (campo "sig"), que o programa exige para
se atualizar sozinho. Os outros programas do catálogo não são tocados.

Uso (depois de packaging/release.sh):
    python3 packaging/site/publish_site.py /caminho/do/PT2VHF-Site
Depois, no repositório do site: git pull --rebase, commit e push na main
(a Hostinger publica cada push).
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from common import ed25519                        # noqa: E402
from common.updater import PUBLIC_KEY, signed_text  # noqa: E402

KEY_PATH = os.environ.get("PT2VHF_SIGNING_KEY", os.path.join(
    os.path.expanduser("~"), ".pt2vhf", "chave-atualizacao.key"))
NOTES = os.path.join(ROOT, "packaging", "site", "novidades.txt")
FOLDER = "downloads/prog-tool"
BASE_URL = f"https://www.pt2vhf.com/{FOLDER}/"


def version() -> str:
    with open(os.path.join(ROOT, "launcher", "__init__.py"),
              encoding="utf-8") as fh:
        return re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)


def file_table(v: str) -> list[tuple[str, str, str, str]]:
    """(categoria, rótulo, arquivo, detalhe) na ordem exigida pelo site."""
    return [
        ("windows-installer", "Windows — Instalador",
         f"PT2VHFProgTool-{v}-instalador.exe",
         "Windows 10/11 64 bits (recomendado)"),
        ("windows-portable", "Windows — Portátil",
         f"PT2VHFProgTool-{v}-windows-portatil.zip",
         "Windows 10/11 64 bits, sem instalação"),
        ("linux-deb", "Linux — .deb (Debian/Ubuntu)",
         f"pt2vhf-prog-tool_{v}_all.deb",
         "Ubuntu 22.04+, Debian 12+, Mint 21+"),
        ("linux-targz", "Linux — .tar.gz",
         f"pt2vhf-prog-tool-{v}-linux.tar.gz",
         "Outras distribuições e macOS (Python 3.10+ com Tkinter)"),
        ("source", "Código-fonte", f"pt2vhf-prog-tool-{v}-codigo-fonte.zip",
         "GPLv3"),
        ("checksums", "Somas de verificação", "SHA256SUMS.txt", ""),
    ]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_key() -> bytes:
    if not os.path.isfile(KEY_PATH):
        raise SystemExit(f"Chave de assinatura não encontrada: {KEY_PATH}")
    with open(KEY_PATH, encoding="ascii") as fh:
        key = base64.b64decode(fh.read().strip())
    if ed25519.public_key(key) != PUBLIC_KEY:
        raise SystemExit("A chave não corresponde à chave pública embutida "
                         "em common/updater.py")
    return key


def publish(site: str, dist: str) -> dict:
    v = version()
    key = load_key()
    catalog_path = os.path.join(site, "updates.json")
    with open(catalog_path, encoding="utf-8") as fh:
        catalog = json.load(fh)
    if catalog.get("schema") != 1 or "prog" not in catalog.get("products",
                                                                {}):
        raise SystemExit("updates.json do site em formato inesperado")
    dest = os.path.join(site, FOLDER)
    os.makedirs(dest, exist_ok=True)
    table = file_table(v)
    wanted = {name for _, _, name, _ in table}
    for _, _, name, _ in table:
        if not os.path.isfile(os.path.join(dist, name)):
            raise SystemExit(f"Falta {name} em {dist} (rode release.sh)")
    for old in os.listdir(dest):            # versão anterior
        if old not in wanted:
            os.remove(os.path.join(dest, old))
    files = []
    for cat, label, name, detail in table:
        src = os.path.join(dist, name)
        shutil.copy2(src, os.path.join(dest, name))
        digest = sha256(src)
        entry = {"category": cat, "label": label, "name": name,
                 "url": BASE_URL + name, "size": os.path.getsize(src),
                 "sha256": digest}
        if detail:
            entry["detail"] = detail
        if cat in ("windows-installer", "windows-portable", "linux-deb",
                   "linux-targz"):
            entry["sig"] = base64.b64encode(
                ed25519.sign(key, signed_text(v, name, digest))).decode()
        files.append(entry)
    notes = []
    if os.path.isfile(NOTES):
        with open(NOTES, encoding="utf-8") as fh:
            notes = [ln.strip("-• \n") for ln in fh if ln.strip()]
    today = datetime.date.today().isoformat()
    prog = catalog["products"]["prog"]
    prog.update({"version": v, "date": today, "notes": "; ".join(notes),
                 "files": files})
    prog.setdefault("page", "https://www.pt2vhf.com/#prog")
    catalog["updated"] = today
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return prog


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    site_dir = sys.argv[1]
    dist_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "dist", "site")
    p = publish(site_dir, dist_dir)
    print(f"Prog Tool {p['version']} preparado em {site_dir}:")
    for f in p["files"]:
        print(f"  {f['name']}  {f['size']} bytes")
    print("Agora: git pull --rebase origin main && git add -A && "
          "git commit && git push origin main")
