"""Atualização automática a partir do site www.pt2vhf.com.

O site publica, na pasta do programa:
    atualizacao.json      versão, novidades e arquivos (com SHA-256)
    atualizacao.json.sig  assinatura Ed25519 do arquivo acima (base64)

O programa só aceita o arquivo se a assinatura conferir com a chave pública
embutida abaixo; depois confere o SHA-256 de cada pacote baixado. Assim,
mesmo que o site seja invadido, ninguém consegue distribuir um instalador
falso sem a chave privada (que fica só com o mantenedor).

O endereço pode ser trocado com a variável de ambiente PT2VHF_UPDATE_URL
(usada nos testes).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import ed25519

UPDATE_URL = "https://www.pt2vhf.com/progtool/atualizacao.json"
PUBLIC_KEY = base64.b64decode("IT4pnH5Zs131x6l9l+0JbckmWiU9C1UQPMQYuctxf8U=")
APP_ID = "pt2vhf-prog-tool"
CHECK_INTERVAL = 24 * 3600
CONFIG = os.path.join(os.path.expanduser("~"), ".ts2000prog", "config.json")


class UpdateError(Exception):
    pass


@dataclass
class UpdateInfo:
    version: str
    date: str
    notes: list[str]
    page: str
    files: dict[str, dict] = field(default_factory=dict)


# ------------------------------------------------------------ utilidades

def parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        raise UpdateError(f"Versão inválida: {v!r}") from None


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def update_url() -> str:
    return os.environ.get("PT2VHF_UPDATE_URL", UPDATE_URL)


def _check_scheme(url: str) -> None:
    u = urllib.parse.urlparse(url)
    local = u.hostname in ("localhost", "127.0.0.1")
    if u.scheme != "https" and not (u.scheme == "http" and local):
        raise UpdateError(f"Endereço não seguro recusado: {url}")


def _open(url: str, timeout: float):
    _check_scheme(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": f"{APP_ID}/{current_version()}"})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _fetch(url: str, timeout: float = 15, limit: int = 1 << 20) -> bytes:
    with _open(url, timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise UpdateError("Arquivo de atualização grande demais")
    return data


def current_version() -> str:
    from launcher import __version__
    return __version__


# ---------------------------------------------------------- configuração

def load_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=1)
    except OSError:
        pass


def auto_check_due(cfg: dict) -> bool:
    if not cfg.get("auto_update", True):
        return False
    return time.time() - float(cfg.get("last_check", 0)) > CHECK_INTERVAL


# -------------------------------------------------------------- consulta

def parse_manifest(data: bytes, signature_b64: bytes, base_url: str,
                   public_key: bytes | None = None) -> UpdateInfo:
    try:
        sig = base64.b64decode(signature_b64.strip(), validate=True)
    except ValueError:
        raise UpdateError("Assinatura em formato inválido") from None
    if not ed25519.verify(public_key or PUBLIC_KEY, data, sig):
        raise UpdateError("Assinatura do arquivo de atualização não confere; "
                          "atualização recusada")
    try:
        m = json.loads(data.decode("utf-8"))
        if m.get("app") != APP_ID:
            raise UpdateError("Arquivo de atualização de outro programa")
        files = {}
        for key, f in m.get("files", {}).items():
            url = urllib.parse.urljoin(base_url, f["file"])
            _check_scheme(url)
            files[key] = {"url": url, "sha256": f["sha256"].lower(),
                          "size": int(f.get("size", 0)),
                          "name": os.path.basename(f["file"])}
        return UpdateInfo(
            version=str(m["version"]), date=str(m.get("date", "")),
            notes=[str(n) for n in m.get("notes", [])],
            page=urllib.parse.urljoin(base_url, m.get("page", "./")),
            files=files)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise UpdateError(f"Arquivo de atualização inválido: {e}") from None


def check(timeout: float = 15) -> UpdateInfo:
    url = update_url()
    try:
        data = _fetch(url, timeout)
        sig = _fetch(url + ".sig", timeout, limit=4096)
    except UpdateError:
        raise
    except Exception as e:      # rede, DNS, HTTP, certificado...
        raise UpdateError(f"Não foi possível consultar {url}: {e}") from None
    return parse_manifest(data, sig, url)


# ------------------------------------------------------- tipo de instalação

def install_kind() -> str:
    """Qual pacote serve para esta instalação."""
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        here = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(here, "Desinstalar.exe")):
            return "windows-instalador"
        return "windows-portatil"
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform.startswith("linux") and \
            here.startswith("/usr/lib/pt2vhf-prog-tool"):
        return "deb"
    return "tgz"


def downloads_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(d) else tempfile.gettempdir()


def download(entry: dict, dest_dir: str, progress=None,
             cancel: threading.Event | None = None) -> str:
    """Baixa o pacote e confere o SHA-256. Devolve o caminho."""
    dest = os.path.join(dest_dir, entry["name"])
    tmp = dest + ".parcial"
    h = hashlib.sha256()
    done = 0
    try:
        with _open(entry["url"], 30) as r, open(tmp, "wb") as fh:
            total = int(r.headers.get("Content-Length") or entry["size"] or 0)
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateError("Download cancelado")
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if h.hexdigest() != entry["sha256"]:
            raise UpdateError("O arquivo baixado está corrompido (SHA-256 "
                              "não confere)")
        os.replace(tmp, dest)
        return dest
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError(f"Falha no download: {e}") from None
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def launch_installer(path: str) -> None:
    """Windows: instala em silêncio e reabre o programa (/AUTOSTART)."""
    subprocess.Popen([path, "/S", "/AUTOSTART"], close_fds=True)


def open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)      # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ------------------------------------------------------------- OTA interno

def app_dir() -> str:
    """Pasta da instalação atual (onde fica o executável ou o main.py)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extract(archive: str, dest: str) -> str:
    """Extrai .zip/.tar.gz com segurança e devolve a pasta raiz extraída."""
    import tarfile
    import zipfile
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            for n in names:
                if not os.path.realpath(os.path.join(dest, n)).startswith(
                        root + os.sep):
                    raise UpdateError("Pacote com caminho inválido")
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                p = os.path.realpath(os.path.join(dest, m.name))
                if not p.startswith(root + os.sep) or m.issym() or m.islnk():
                    raise UpdateError("Pacote com caminho inválido")
            t.extractall(dest)
    entries = [e for e in os.listdir(dest) if not e.startswith(".")]
    if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        return os.path.join(dest, entries[0])
    return dest


def _copy_tree(src: str, dst: str) -> None:
    import shutil
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            _copy_tree(s, d)
        else:
            shutil.copy2(s, d)


def apply_update(path: str, kind: str) -> str:
    """Instala o pacote baixado sem sair do programa (quando possível).

    Devolve "restart" (reabra o programa: o chamador sai e relança),
    "exit" (um instalador externo vai reabrir o programa; apenas saia) ou
    "manual" (o arquivo foi aberto/salvo; o usuário conclui).
    """
    if kind == "windows-instalador":
        launch_installer(path)
        return "exit"
    if kind == "windows-portatil":
        new = _extract(path, tempfile.mkdtemp(prefix="pt2vhf-ota-"))
        exe = os.path.join(app_dir(), os.path.basename(sys.executable))
        bat = os.path.join(tempfile.gettempdir(), "pt2vhf-ota.bat")
        with open(bat, "w", encoding="mbcs" if sys.platform == "win32"
                  else "utf-8") as fh:
            fh.write(
                "@echo off\r\n"
                f":espera\r\ntasklist /FI \"PID eq {os.getpid()}\" | "
                f"find \"{os.getpid()}\" >nul && (timeout /t 1 >nul & "
                "goto espera)\r\n"
                f"robocopy \"{new}\" \"{app_dir()}\" /E /R:3 /W:1 >nul\r\n"
                f"start \"\" \"{exe}\"\r\n"
                f"rmdir /S /Q \"{os.path.dirname(new)}\"\r\n"
                "del \"%~f0\"\r\n")
        subprocess.Popen(["cmd", "/c", bat], close_fds=True,
                         creationflags=getattr(subprocess,
                                               "CREATE_NO_WINDOW", 0))
        return "exit"
    if kind == "tgz":
        target = app_dir()
        if not os.access(target, os.W_OK):
            open_path(os.path.dirname(path))
            return "manual"
        new = _extract(path, tempfile.mkdtemp(prefix="pt2vhf-ota-"))
        if not os.path.isfile(os.path.join(new, "main.py")):
            raise UpdateError("Pacote .tar.gz sem main.py")
        _copy_tree(new, target)
        return "restart"
    if kind == "deb":
        import shutil
        if shutil.which("pkexec"):
            r = subprocess.run(["pkexec", "apt-get", "install", "-y", path])
            if r.returncode == 0:
                return "restart"
            raise UpdateError("A instalação do pacote foi cancelada ou "
                              "falhou")
        open_path(path)
        return "manual"
    open_path(path)
    return "manual"


def restart() -> None:
    """Reabre o programa (após OTA em .tar.gz ou .deb)."""
    if getattr(sys, "frozen", False):
        args = [sys.executable]
    elif install_kind() == "deb":
        args = ["/usr/bin/pt2vhf-prog-tool"]
    else:
        args = [sys.executable, os.path.join(app_dir(), "main.py")]
    subprocess.Popen(args, close_fds=True)
    os._exit(0)


KIND_LABELS = {
    "windows-instalador": "Windows (instalado)",
    "windows-portatil": "Windows (portátil)",
    "deb": "Linux (pacote .deb)",
    "tgz": "Código-fonte / .tar.gz",
}
