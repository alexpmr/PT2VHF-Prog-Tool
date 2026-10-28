# Instruções para o Claude

## Fluxo de trabalho (preferência do mantenedor)

Sempre faça o ciclo completo sem parar para pedir confirmação:
implementar → testar (`python3 -m unittest discover -s tests`) → commit →
push no GitHub (`alexpmr/PT2VHF-Prog-Tool`, branch `main`) → gerar os
pacotes → publicar.

- **Só GitHub.** O mantenedor não usa GitLab: nunca use, sugira nem mencione
  GitLab (remotos, tokens, pipelines, releases ou checagens).
- **Publicar uma versão:**
  1. Suba `__version__` em `launcher/__init__.py` e o `VERSION` padrão em
     `packaging/windows/installer.nsi`; escreva as novidades em
     `packaging/site/novidades.txt`.
  2. `packaging/release.sh` (Windows via Wine + Linux + página do site).
     Requer a chave de assinatura em `~/.pt2vhf/chave-atualizacao.key`
     (nunca commitar; o mantenedor guarda o arquivo).
  3. Publique no site: clone `alexpmr/PT2VHF-Site` (precisa de acesso de
     escrita), rode `python3 packaging/site/publish_site.py <clone>` e, no
     clone, `git pull --rebase origin main`, commit e `git push origin main`
     (a Hostinger publica cada push; nunca use `--force`). O script copia os
     pacotes para `downloads/prog-tool/` e atualiza `products.prog` do
     `updates.json`, com a assinatura `sig` de cada pacote — é esse catálogo
     que o programa consulta para o OTA. Siga também o README do site.
- Interface e mensagens em português do Brasil.
