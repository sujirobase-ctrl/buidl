# Correções de hosts sobre a release v1.3.0

Este documento registra a primeira rodada de correções de hosts. A revisão
posterior de downloads longos adiciona recuperação automática da GUI,
checkpoints por arquivo, cookies recarregáveis, assinatura tardia do Bunkr e
agendamento limitado. Consulte `tests/LONG_SESSIONS_QA.md` e o relatório da
entrega `Correcoes/BUIDL-1.3.0-Downloads-Longos/Documentacao/` para os resultados atuais.

## Base confirmada

- Release: https://github.com/sujirobase-ctrl/buidl/releases/tag/v1.3.0
- Commit base: `077fe0d1f4b57a92b953eeede1e3304fd75756aa`.
- Os 24 arquivos Python em `src/` do wheel anexado à release foram comparados
  com a tag e são idênticos, desconsiderando apenas os finais de linha.
- Branch local: `codex/v130-host-updates`. As alterações locais da outra pasta,
  identificadas como 1.5.0/1.5.2-mobile, não foram incorporadas nem modificadas.
- Referência upstream: ForumPostDownloader 3.23, commit
  `3844058597cef20ff18d2c84afdec5fcb11801ee`.

## Implementação

- Bunkr: endpoint `apidl.bunkr.ru`, cabeçalhos de origem/referência atuais,
  extração de `data-file-id`, respostas com URL criptografada por XOR,
  assinatura de CDN, preservação dos parâmetros da URL e do nome do arquivo.
- Compatibilidade com respostas antigas, links antigos de CDN, domínios novos,
  álbuns paginados e deduplicação; uma falha de rede em um item não descarta os demais.
- GoFile: Node incluído em GUI, CLI e batch de Windows, preferido em relação
  ao PATH, com timeout de execução e licença correspondente incluída no pacote.
- Goonbox: aviso de qualidade no log do aplicativo quando a mídia resolvida é
  uma miniatura. O arquivo original continua sendo preferido.
- CI: instalação explícita do Node e teste do runtime nos três executáveis;
  execução do teste completo com servidor local, além da suíte offline.

## Validação realizada

Ambiente local: Windows, Python 3.12, Node 24.22.1, dependências respeitando
`requirements.txt` da release.

- `python -m pytest tests --ignore=tests/test_e2e.py -q`: 128 testes aprovados.
- `python -X utf8 -m tests.test_e2e`: 32 verificações aprovadas; análise de
  thread, download, tamanhos, retomada, filtros e dry-run em servidor local.
- GUI, CLI e batch compilados com PyInstaller.
- `tests/packaged_gofile_smoke.py`: aprovado nos três executáveis; executa o
  Node extraído do pacote com PATH vazio e usa o resolver extraído do próprio EXE.
- `tests/packaged_video_smoke.py`: aprovado; 16 frames decodificados com o
  PyAV efetivamente extraído do executável da GUI.
- CLI empacotada: `--help` executou com sucesso.
- Simulação de galeria `tests/gui_preview_smoke.py`: aprovada, com janelas Tk,
  paginação, filtros, seleção, vídeo, cache e layout. Os dados desse smoke são simulados.
- Fluxo completo `tests/gui_local_e2e.py`: 25 verificações aprovadas, usando
  o código compilado de GUI/src extraído do EXE em uma janela Tk de testes.
  Houve análise de duas páginas, prévia/pausa de vídeo, download de três mídias
  artificiais via HTTP local, conferência dos hashes, reexecução sem duplicar
  arquivos e cancelamento da galeria. O downloader e o HTTP não foram substituídos.
- As capturas e o JSON dessa execução ficam em `Documentacao/GUI-QA-2026-10-28/`
  na entrega de correções. Instruções reproduzíveis em `tests/GUI_QA.md`.
- GoFile real: o resultado do cálculo Python coincidiu com o JavaScript
  obtido de `https://gofile.io/js/wt.obf.js`, usando um token sintético.
- `pip check` e `git diff --check`: aprovados.

## Limites da validação

- A consulta POST à API real do Bunkr respondeu HTTP 403 neste ambiente.
  O protocolo foi validado com respostas simuladas; não foi confirmado um
  download completo de mídia real de Bunkr, GoFile ou Goonbox.
- Não foi gerado/testado um APK. No Android, a descoberta dinâmica do salt
  GoFile continua dependendo de um runtime JavaScript disponível; sem ele,
  usa o último salt conhecido e emite um aviso.
- Goonbox continua sujeito a bloqueios de Cloudflare; não foi implementada
  uma integração com aba autenticada de navegador.
- Perfis Redgifs, Yandex e Give.xxx permanecem fora deste conjunto de correções.
- O projeto conserva a numeração 1.3.0. Os arquivos com `host-updates` no nome
  são builds locais modificados, e não os binários originais publicados.
- Nada foi publicado no GitHub.
