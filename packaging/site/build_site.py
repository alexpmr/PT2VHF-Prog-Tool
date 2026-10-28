"""Monta a página de download em dist/site/ a partir dos pacotes de dist/.

Uso (na raiz, depois de gerar os pacotes):  python3 packaging/site/build_site.py

Resultado: dist/site/ (index.html, pacotes, imagens, SHA256SUMS.txt) e
dist/site.zip para enviar à hospedagem.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import os
import re
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DIST = os.path.join(ROOT, "dist")
SITE = os.path.join(DIST, "site")

with open(os.path.join(ROOT, "launcher", "__init__.py"),
          encoding="utf-8") as fh:
    VERSION = re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)

FILES = {
    "win": f"PT2VHFProgTool-{VERSION}-instalador.exe",
    "winzip": f"PT2VHFProgTool-{VERSION}-windows-portatil.zip",
    "deb": f"pt2vhf-prog-tool_{VERSION}_all.deb",
    "tgz": f"pt2vhf-prog-tool-{VERSION}-linux.tar.gz",
    "src": f"pt2vhf-prog-tool-{VERSION}-codigo-fonte.zip",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    return f"{n / 1e6:.1f} MB".replace(".", ",") if n >= 1e6 else \
        f"{n / 1e3:.0f} KB"


def prepare() -> dict[str, dict]:
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "img"))
    # código-fonte (exigido pela GPL ao distribuir os executáveis)
    subprocess.run(["git", "archive", "--format=zip",
                    f"--prefix=pt2vhf-prog-tool-{VERSION}/",
                    "-o", os.path.join(DIST, FILES["src"]), "HEAD"],
                   cwd=ROOT, check=True)
    info = {}
    for key, name in FILES.items():
        src = os.path.join(DIST, name)
        if not os.path.isfile(src):
            raise SystemExit(f"Falta o arquivo {name} em dist/")
        shutil.copy2(src, os.path.join(SITE, name))
        info[key] = {"name": name, "size": human(os.path.getsize(src)),
                     "sha": sha256(src)}
    with open(os.path.join(SITE, "SHA256SUMS.txt"), "w") as fh:
        for v in info.values():
            fh.write(f"{v['sha']}  {v['name']}\n")
    for f in os.listdir(os.path.join(ROOT, "docs", "site")):
        shutil.copy2(os.path.join(ROOT, "docs", "site", f),
                     os.path.join(SITE, "img", f))
    shutil.copy2(os.path.join(ROOT, "assets", "app.png"),
                 os.path.join(SITE, "img", "icone.png"))
    return info


PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PT2VHF Prog Tool</title>
<meta name="description" content="Programador gratuito para Kenwood TS-2000 (memórias, menus e display em tempo real) e Icom ID-51A Plus2 / ID-880H (memórias por clonagem).">
<link rel="icon" href="img/icone.png">
<style>
:root {
  --bg: #f4f6f9; --surface: #ffffff; --text: #1d2433; --muted: #5d6678;
  --line: #d9dee6; --accent: #e08a12; --accent-ink: #1a0f00;
  --brand: #1d2433; --ok: #1f7a3d; --warn-bg: #fff6e5; --warn-line: #f0c36d;
  --code: #eef1f5; --shadow: 0 1px 3px rgba(20,30,50,.08), 0 6px 24px rgba(20,30,50,.06);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f141c; --surface: #171e29; --text: #e6eaf1; --muted: #9aa5b8;
    --line: #2a3443; --accent: #f0a030; --accent-ink: #1a0f00;
    --brand: #0b1018; --ok: #5bc27f; --warn-bg: #2a2212; --warn-line: #7a5a1c;
    --code: #222b38; --shadow: none;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
a { color: inherit; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 16px; }
header.hero { background: var(--brand); color: #fff; padding: 40px 0 44px; }
.hero .wrap { display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
.hero img { width: 88px; height: 88px; }
.hero h1 { margin: 0; font-size: clamp(28px, 4vw, 40px); line-height: 1.15; }
.hero p { margin: 6px 0 0; color: #c9d1de; max-width: 640px; }
.hero .meta { font-size: 14px; color: #9aa7bb; margin-top: 10px; }
.cta { margin-top: 18px; display: flex; gap: 10px; flex-wrap: wrap; }
.btn { display: inline-flex; align-items: center; gap: 8px; padding: 11px 18px;
  border-radius: 8px; font-weight: 600; text-decoration: none; border: 1px solid transparent; }
.btn-primary { background: var(--accent); color: var(--accent-ink); }
.btn-primary:hover { filter: brightness(1.06); }
.btn-ghost { border-color: #4a5568; color: #fff; }
.btn-ghost:hover { background: rgba(255,255,255,.06); }
main section { padding: 40px 0 8px; }
h2 { font-size: 24px; margin: 0 0 6px; }
.lead { color: var(--muted); margin: 0 0 20px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  padding: 18px; box-shadow: var(--shadow); display: flex; flex-direction: column; }
.card h3 { margin: 0 0 4px; font-size: 18px; }
.card .os { font-size: 13px; color: var(--muted); }
.card p { margin: 10px 0 14px; color: var(--muted); font-size: 15px; flex: 1; }
.card .btn { justify-content: center; background: var(--surface); border-color: var(--line); color: var(--text); }
.card .btn:hover { border-color: var(--accent); }
.card.rec { border-color: var(--accent); }
.card.rec .btn { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.tag { display: inline-block; font-size: 12px; font-weight: 700; color: var(--accent-ink);
  background: var(--accent); border-radius: 99px; padding: 1px 9px; margin-left: 6px; vertical-align: 2px; }
.sha { margin-top: 10px; font: 11px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--muted); word-break: break-all; }
.feat { display: grid; gap: 22px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.feat figure { margin: 0; background: var(--surface); border: 1px solid var(--line);
  border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.feat img { display: block; width: 100%; height: auto; border-bottom: 1px solid var(--line); }
.feat figcaption { padding: 14px 16px 16px; font-size: 15px; color: var(--muted); }
.feat figcaption b { display: block; color: var(--text); font-size: 16px; margin-bottom: 2px; }
.wide { grid-column: 1 / -1; }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 0 16px; margin-bottom: 10px; }
summary { cursor: pointer; padding: 14px 0; font-weight: 600; }
details[open] summary { border-bottom: 1px solid var(--line); margin-bottom: 8px; }
details ol, details ul { padding-left: 20px; }
code { background: var(--code); padding: 1px 6px; border-radius: 5px;
  font: 14px ui-monospace, SFMono-Regular, Consolas, monospace; }
.warn { background: var(--warn-bg); border: 1px solid var(--warn-line); border-radius: 10px; padding: 14px 16px; }
.warn ul { margin: 6px 0 0; padding-left: 20px; }
footer { border-top: 1px solid var(--line); margin-top: 40px; padding: 24px 0 40px;
  color: var(--muted); font-size: 14px; }
@media (max-width: 560px) { .hero img { width: 64px; height: 64px; } }
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <img src="img/icone.png" alt="">
    <div>
      <h1>PT2VHF Prog Tool</h1>
      <p>Programação gratuita do <b>Kenwood TS-2000</b> (memórias, menus e display LCD em tempo real) e dos <b>Icom ID-51A Plus2</b> e <b>ID-880H</b> (memórias por clonagem).</p>
      <div class="meta">Versão __VERSION__ · __DATE__ · Windows e Linux · Software livre (GPLv3)</div>
      <div class="cta">
        <a class="btn btn-primary" id="main-dl" href="__WIN__">Baixar para Windows</a>
        <a class="btn btn-ghost" href="#downloads">Outras versões</a>
      </div>
    </div>
  </div>
</header>

<main class="wrap">
  <section id="downloads">
    <h2>Downloads</h2>
    <p class="lead">Escolha a versão do seu sistema. O código SHA-256 de cada arquivo está no cartão e em <a href="SHA256SUMS.txt">SHA256SUMS.txt</a>.</p>
    <div class="grid">
      <div class="card rec" data-os="win">
        <h3>Windows <span class="tag">recomendado</span></h3>
        <div class="os">Windows 10 e 11, 64 bits · __WIN_SIZE__ · lançado em __DATE__</div>
        <p>Instalador com atalhos no Menu Iniciar e desinstalação pelo Painel. Não precisa de Python.</p>
        <a class="btn" href="__WIN__" download>Baixar instalador</a>
        <div class="sha">SHA-256: __WIN_SHA__</div>
      </div>
      <div class="card" data-os="win">
        <h3>Windows portátil</h3>
        <div class="os">Windows 10 e 11, 64 bits · __WINZIP_SIZE__ · lançado em __DATE__</div>
        <p>Sem instalação: descompacte e abra <code>PT2VHFProgTool.exe</code>. Bom para pen drive.</p>
        <a class="btn" href="__WINZIP__" download>Baixar .zip</a>
        <div class="sha">SHA-256: __WINZIP_SHA__</div>
      </div>
      <div class="card" data-os="linux">
        <h3>Ubuntu, Debian, Mint</h3>
        <div class="os">Ubuntu 22.04+, Debian 12+, Mint 21+ · __DEB_SIZE__ · lançado em __DATE__</div>
        <p>Pacote <code>.deb</code>: instala dependências, ícone e atalho no menu de aplicativos.</p>
        <a class="btn" href="__DEB__" download>Baixar .deb</a>
        <div class="sha">SHA-256: __DEB_SHA__</div>
      </div>
      <div class="card" data-os="linux">
        <h3>Outras distribuições / macOS</h3>
        <div class="os">Python 3.10+ com Tkinter · __TGZ_SIZE__ · lançado em __DATE__</div>
        <p>Para Fedora, Arch, openSUSE e macOS (avançado). Descompacte e rode <code>./pt2vhf-prog-tool.sh</code>.</p>
        <a class="btn" href="__TGZ__" download>Baixar .tar.gz</a>
        <div class="sha">SHA-256: __TGZ_SHA__</div>
      </div>
    </div>
  </section>

  <section id="recursos">
    <h2>O que ele faz</h2>
    <p class="lead">Uma tela inicial para escolher o fabricante e o rádio. Cada rádio abre seu próprio editor.</p>
    <div class="feat">
      <figure>
        <img src="img/inicio.png" alt="Tela inicial com os botões Kenwood e ICOM" width="820" height="520" loading="lazy">
        <figcaption><b>Escolha o rádio</b>Kenwood → TS-2000; ICOM → ID-51A Plus2 e ID-880H.</figcaption>
      </figure>
      <figure>
        <img src="img/ts2000_memorias.png" alt="Editor de memórias do TS-2000" width="1200" height="640" loading="lazy">
        <figcaption><b>Kenwood TS-2000</b>300 memórias (frequência, split, modo, tons/DCS, shift, passo, grupo, nome) e menus. Lê e grava pela serial: tudo, só o que mudou ou só o selecionado.</figcaption>
      </figure>
      <figure class="wide">
        <img src="img/display_ambar.png" alt="Display LCD em tempo real, tema âmbar" width="1000" height="330" loading="lazy">
        <figcaption><b>Display em tempo real</b>Um segundo display do TS-2000 na tela do computador: frequência, modo, RX/TX, VFO/memória, split, RIT/XIT, S-meter e potência. Temas âmbar, verde, azul e vermelho, e tela cheia (F11) para um segundo monitor.</figcaption>
      </figure>
      <figure>
        <img src="img/display_azul_tx.png" alt="Display em transmissão, tema azul noturno" width="1000" height="330" loading="lazy">
        <figcaption><b>Transmitindo</b>Durante a TX, o S-meter vira medidor de potência.</figcaption>
      </figure>
      <figure>
        <img src="img/icom_id51.png" alt="Editor de memórias do Icom ID-51A Plus2" width="1200" height="600" loading="lazy">
        <figcaption><b>Icom ID-51A Plus2 e ID-880H</b>Memórias, bancos e campos D-STAR (UR/RPT1/RPT2). Clona do rádio e para o rádio, e abre/salva arquivos <code>.icf</code>.</figcaption>
      </figure>
    </div>
  </section>

  <section id="instalar">
    <h2>Instalação</h2>
    <details>
      <summary>Windows</summary>
      <ol>
        <li>Baixe e abra o instalador.</li>
        <li>Se aparecer "O Windows protegeu o computador", clique em <b>Mais informações</b> e depois em <b>Executar assim mesmo</b>. O aviso aparece porque o instalador não tem assinatura digital paga; confira o SHA-256 se quiser.</li>
        <li>Instale o driver do seu cabo USB-serial (FTDI, Prolific, Silicon Labs ou o do cabo Icom). A porta aparece como <code>COM3</code>, <code>COM4</code> etc. na lista <b>Porta</b>.</li>
      </ol>
    </details>
    <details>
      <summary>Ubuntu, Debian e Mint</summary>
      <ol>
        <li>Instale com <code>sudo apt install ./__DEB__</code> (ou dê dois cliques no arquivo).</li>
        <li>Libere a porta serial para seu usuário: <code>sudo usermod -aG dialout $USER</code> e entre de novo na sessão.</li>
        <li>Abra <b>PT2VHF Prog Tool</b> no menu de aplicativos.</li>
      </ol>
    </details>
    <details>
      <summary>Outras distribuições Linux e macOS</summary>
      <ol>
        <li>Instale o Python 3.10+ com Tkinter (Fedora: <code>python3-tkinter</code>; Arch: <code>tk</code>; macOS: Python de python.org).</li>
        <li>Descompacte: <code>tar xzf __TGZ__</code></li>
        <li>Rode: <code>./pt2vhf-prog-tool-__VERSION__/pt2vhf-prog-tool.sh</code> (instala o pyserial se faltar).</li>
      </ol>
    </details>
    <details>
      <summary>Testar sem rádio</summary>
      <p>Em qualquer editor, escolha a porta <code>SIMULADOR</code>. O TS-2000 simulado tem memórias de exemplo, menus e um display que sintoniza, recebe e transmite sozinho.</p>
    </details>
  </section>

  <section id="avisos">
    <h2>Antes de gravar no seu rádio</h2>
    <div class="warn">
      Este é um programa novo, testado com rádios simulados e comparado com o CHIRP, mas ainda não com todos os rádios reais.
      <ul>
        <li><b>Faça backup primeiro:</b> leia o rádio e salve o arquivo (<code>.ts2k</code> no TS-2000, <code>.icf</code> nos Icom) antes da primeira gravação.</li>
        <li><b>Menus do TS-2000:</b> a tabela segue o manual do rádio; leia e salve o backup antes de gravar menus em massa.</li>
        <li><b>Icom:</b> a clonagem grava a memória inteira do rádio. Use sempre uma imagem lida do próprio rádio ou um <code>.icf</code> do mesmo modelo.</li>
      </ul>
    </div>
  </section>

  <section id="fonte">
    <h2>Código-fonte e licença</h2>
    <p class="lead">Software livre sob a licença GNU GPL versão 3. Os mapas de memória dos rádios Icom foram derivados do projeto <a href="https://chirpmyradio.com">CHIRP</a> (GPLv3).</p>
    <p><a class="btn" style="border:1px solid var(--line);background:var(--surface)" href="__SRC__" download>Baixar código-fonte (__SRC_SIZE__)</a></p>
  </section>
</main>

<footer>
  <div class="wrap">PT2VHF Prog Tool __VERSION__ · Kenwood e Icom são marcas de seus respectivos donos; este programa não é afiliado a elas.</div>
</footer>

<script>
(function () {
  var ua = navigator.userAgent || "";
  var linux = /Linux/i.test(ua) && !/Android/i.test(ua);
  var mac = /Mac OS X|Macintosh/i.test(ua) && !/iPhone|iPad/i.test(ua);
  if (!linux && !mac) return;
  var btn = document.getElementById("main-dl");
  var ubuntu = /Ubuntu|Debian|Mint/i.test(ua);
  btn.textContent = mac ? "Baixar para macOS" : "Baixar para Linux";
  btn.href = (linux && ubuntu) ? "__DEB__" : "__TGZ__";
  document.querySelectorAll(".card").forEach(function (c) {
    c.classList.toggle("rec", c.dataset.os === "linux" &&
      (mac ? c.querySelector("a").getAttribute("href") === "__TGZ__" : true));
  });
})();
</script>
</body>
</html>
"""


def build() -> None:
    info = prepare()
    page = PAGE
    subs = {"__VERSION__": VERSION,
            "__DATE__": datetime.date.today().strftime("%d/%m/%Y")}
    for key, v in info.items():
        k = key.upper()
        subs[f"__{k}_SIZE__"] = v["size"]
        subs[f"__{k}_SHA__"] = v["sha"]
        subs[f"__{k}__"] = html.escape(v["name"])
    # chaves mais longas primeiro (__WINZIP__ antes de __WIN__)
    for k in sorted(subs, key=len, reverse=True):
        page = page.replace(k, subs[k])
    leftover = re.findall(r"__[A-Z_]+__", page)
    if leftover:
        raise SystemExit(f"Marcadores não substituídos: {leftover}")
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    out = os.path.join(DIST, "site.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(SITE):
            for f in files:
                p = os.path.join(dirpath, f)
                z.write(p, os.path.relpath(p, SITE))
    print(f"Página: {SITE}/index.html")
    print(f"Pacote para upload: {out}")


if __name__ == "__main__":
    build()
