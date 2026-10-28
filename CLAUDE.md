# Instruções para o Claude

## Fluxo de trabalho (preferência do mantenedor)

Sempre faça o ciclo completo sem parar para pedir confirmação:
implementar → testar (`python3 -m unittest discover -s tests`) → commit →
push no GitHub (`alexpmr/PT2VHF-Prog-Tool`, branch `main`) → gerar os
pacotes → publicar.

- **Só GitHub.** O GitLab foi aposentado; não use.
- **Publicar uma versão:**
  1. Suba `__version__` em `launcher/__init__.py` e o `VERSION` padrão em
     `packaging/windows/installer.nsi`; escreva as novidades em
     `packaging/site/novidades.txt`.
  2. `packaging/release.sh` (Windows via Wine + Linux + página do site).
     Requer a chave de assinatura em `~/.pt2vhf/chave-atualizacao.key`
     (nunca commitar; o mantenedor guarda o arquivo).
  3. Crie a tag `vX.Y.Z` e a Release no GitHub com os arquivos de
     `dist/site/` anexados.
  4. Publique `dist/site/` na pasta `/progtool/` do site www.pt2vhf.com
     (é de lá que o programa busca `atualizacao.json` para o OTA).
- Interface e mensagens em português do Brasil.
