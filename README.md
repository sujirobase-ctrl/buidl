# BUIDL — GUI e CLI

## Prévia visual e download seletivo (v1.3.0)

Abra `buidl-gui.exe` (ou execute `python gui.py`), informe a URL da thread,
os cookies quando necessários e a pasta de destino.

- **Visualizar e escolher** analisa as páginas e abre uma galeria antes do download.
- A seleção começa vazia; marque somente os itens desejados ou use **Baixar todos**.
- Busque por nome, post ou host; filtre imagens, vídeos, áudios ou arquivos.
- **Marcar/Desmarcar resultados** afeta todos os resultados do filtro, não só a página visível.
- **Baixar selecionados** respeita a seleção, inclusive itens em outras páginas/filtros.
- **Baixar todos** inclui toda a fila analisada; o botão da tela inicial baixa sem abrir a galeria.
- **Voltar sem baixar** cancela a prévia sem criar estado de conclusão dos arquivos.
- Reabrir **Visualizar e escolher** reutiliza a última análise, miniaturas em cache,
  seleção, filtros e posição na galeria, enquanto o aplicativo continuar aberto.
- **Atualizar thread**, dentro da galeria, busca novamente as páginas e os links.
  Mudanças na URL, cookies ou opções que alteram a lista/destino também refazem a análise.
  Velocidade, tentativas e número de conexões não obrigam uma nova busca.

As miniaturas são carregadas sob demanda, somente em memória, com limite de 4 MiB
por imagem. Em **Vídeos**, clique em **Prévia do vídeo** para reproduzir um trecho
de até 6 segundos, sem áudio, com pausa e repetição. A prévia tem resolução reduzida;
não é um player do vídeo completo. O carregamento usa requisições por trechos,
orçamento de 24 MiB e prazo de 20 segundos verificado entre operações (uma operação
de rede/decodificação em andamento pode levar um pouco mais para terminar).

Se o host bloquear a prévia, exigir login ou não oferecer um formato compatível,
a capa disponível é mantida. Se também não houver capa, aparece um cartão de vídeo.
Isso **não conta como falha de download** nem impede selecionar/baixar o arquivo.
Os dois últimos resultados de vídeo ficam em memória ao reabrir a galeria;
**Tentar novamente** refaz apenas a prévia, sem analisar a thread novamente.
Fechar o player cancela o carregamento e mantém a seleção. Os codecs necessários
estão incluídos no EXE; não é preciso instalar um player externo.
Não há visualização do conteúdo de ZIPs. Alguns hosts só informam o nome final
ao gerar o link e podem aparecer inicialmente em **Arquivos**.

Para retomar uma execução anterior, mantenha a mesma pasta em **Salvar em**.
A fila preparada usa as opções informadas antes da análise; feche a prévia para
alterá-las e analisar novamente.

## Aplicativo Android

O projeto Android está em [android/README.md](android/README.md). Ele usa uma
interface nativa com o mesmo núcleo Python, permite analisar/selecionar arquivos,
capturar cookies pelo navegador interno, escolher a pasta de destino, baixar,
retomar e exportar os downloads pelo seletor do Android.
O APK é de teste/debug para Android 7+ em arm64 ou x86_64.

## Downloads prontos

As versões publicadas ficam em [GitHub Releases](https://github.com/sujirobase-ctrl/buidl/releases).
Cada release inclui o APK Android, `buidl-gui.exe`, CLI, modo batch, wheel Python,
um ZIP portátil dos executáveis e arquivos SHA-256 para conferência.

O workflow em `.github/workflows/build.yml` executa os testes offline e recria
todos esses artefatos em runners limpos. Pushes e pull requests geram artefatos
do Actions; uma tag `vX.Y.Z`, igual à versão do `pyproject.toml`, também publica
a release automaticamente.

## CLI


The userscript's thread parser, host matcher table and per-host resolvers are
reimplemented in Python; the live Rich UI — `Overall Progress` / `File Progress`
panels plus a rolling `Log Messages` panel and a results summary — follows
BunkrDownloader.

```
┌────────── Overall Progress ──────────┐┌─────────── File Progress ───────────┐
│                                      ││                                     │
│ My Test Thread Pack   ━━━━━━━━━ 100% ││ File 3/5  ━━━━━━━━━━  62% • 0:00:03 │
│                                      ││                                     │
└──────────────────────────────────────┘└─────────────────────────────────────┘
┌─────────────────────────────── Log Messages ────────────────────────────────┐
│ 22:07:13 Downloaded      album1.jpg                                         │
│ 22:07:13 Results summary Completed: 5                                       │
│                          Skipped  : 0                                       │
│                          Failed   : 0                                       │
└─────────────────────────────────────────────────────────────────────────────┘
ForumPostDownloader CLI v1.0.0
```

## Install

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
```

Requires Python 3.9+.

## Single URL

```bash
python downloader.py <thread_url>
```

Example:

```bash
python downloader.py "https://forum.example/threads/some-thread.12345/" --all-pages
```

## Batch mode

Put one thread URL per line in `URLs.txt` (blank lines and `#` comments are ignored):

```
# my list
https://forum.example/threads/thread-one.111/
https://forum.example/threads/thread-two.222/
```

Then:

```bash
python main.py --all-pages
```

## File Download Location

With `--custom-path <path>`, files go to `<path>/Downloads`. Otherwise a
`Downloads` folder is created in the script's directory. Layout:

```
Downloads/
└── <Thread Title>/
    ├── photo1.jpg
    ├── clip.mp4
    └── .fpd_state.json     # resume sidecar
```

With `--separate-posts` each post gets its own subfolder (`post-1/`, `post-2/`…).
Album hosts create a subfolder per album unless `--flat` is passed.

## Options

| Option | Description |
| --- | --- |
| `--custom-path <path>` | Base directory; files land in `<path>/Downloads`. |
| `--cookies <file>` | Netscape `cookies.txt`, for login-gated forums. |
| `--no-cookies` | Run anonymously; skip the cookie prompt. |
| `--reset-cookies` | Forget the saved cookies path and ask again. |
| `--all-pages` | Follow pagination to the end of the thread. |
| `--max-pages <n>` | Pages to walk when `--all-pages` is off (default: 1). |
| `--post <id>` | Only download this post id/number. Repeatable. |
| `--include <substr>` | Only files whose name contains this. Repeatable. |
| `--ignore <substr>` | Skip files whose name contains this. Repeatable. |
| `--workers <n>` | Concurrent file downloads (default: 3). |
| `--max-retries <n>` | Retries per file (default: 5). |
| `--separate-posts` | One subfolder per post. |
| `--flat` | Ignore album subfolders. |
| `--dry-run` | Resolve and list files without downloading. |
| `--disable-ui` | Plain log lines instead of the live UI (notebooks, CI). |
| `--log-file <path>` | Where to append the run log (default: `session.log`). |
| `-v`, `--verbose` | Also log every resolved link, queued file and filter hit. |

### Examples

```bash
# Whole thread, images only, into an external drive
python downloader.py <url> --all-pages --include .jpg --include .png --custom-path /mnt/drive

# One specific post, no video
python downloader.py <url> --post 1234 --ignore .mp4

# Preview what would be downloaded
python downloader.py <url> --all-pages --dry-run
```

## Resume

Every thread folder holds a `.fpd_state.json` sidecar recording each item's
outcome. Re-running the same URL skips items already marked `completed`
(reported as `Skipped / Already downloaded`), so interrupted runs pick up where
they left off. Delete the sidecar to force a full re-download.

## Login-gated forums (cookies)

Most forums return **403** to anonymous requests. The first time you run the
tool it asks for a cookies file:

```
┌─────────────────────── Cookies needed ───────────────────────┐
│  How to export cookies                                        │
│    1. Install a cookies.txt extension in the browser where    │
│       you are logged in:                                      │
│       • Chrome/Edge — "Get cookies.txt LOCALLY"               │
│       • Firefox     — "cookies.txt"                           │
│    2. Open the forum and make sure you are logged in.         │
│    3. Click the extension → Export / Download → save it.      │
│    4. Paste the full path to that file below.                 │
└───────────────────────────────────────────────────────────────┘
Path to cookies.txt  (or press Enter to skip):
```

Paste the path (quotes and `~` are handled). The file is validated immediately —
a wrong path or a badly exported file is reported and it asks again, rather than
failing halfway through a download.

The choice is saved to `~/.forumpostdownloader/config.json`, so **you are only
asked once**. Related flags:

| Flag | Effect |
| --- | --- |
| `--cookies <file>` | Use this file; skips the prompt and remembers it. |
| `--no-cookies` | Run anonymously, no prompt. |
| `--reset-cookies` | Forget the saved path and ask again. |

Set `FPD_NO_PROMPT=1` to disable prompting entirely (cron, CI).

If a forum needs a login and no cookies were supplied, the log says so
explicitly (`Access denied` / `Login required`) instead of silently reporting an
empty thread.

### Exporting cookies

1. Install a cookies.txt extension — Chrome/Edge: *Get cookies.txt LOCALLY*;
   Firefox: *cookies.txt*.
2. Log in to the forum in that browser.
3. Open the forum tab, click the extension, export/download.
4. Give the tool that file's path.

The format must be Netscape (TAB-separated). Session cookies exported with
`expires=0` are handled correctly.

## Supported hosts

Host matchers are ported from the userscript's `hosts` table in
[`src/config.py`](src/config.py); per-host resolvers live in
[`src/resolvers.py`](src/resolvers.py):

bunkr · cyberdrop · pixeldrain · gofile · erome · redgifs · saint · imgur ·
postimg · pixhost · imgbox · ibb.co · jpg.church family · pixl.li · img.kiwi ·
imagebam · imagevenue · coomer/kemono · reddit · twimg · nitter · plus a
direct-link fallback for any absolute URL ending in a known media extension.

Unknown hosts are ignored rather than failing the run. Adding a host means one
entry in `HOSTS` and, if the page needs unwrapping, one resolver function.

## Logging

Every event shown on screen is also appended to a log file — no flag needed.
By default that is `session.log` in the current directory.

```bash
python downloader.py <url> --log-file C:/logs/forum.log   # custom destination
python downloader.py <url> --verbose                      # or -v
```

`--log-file` creates missing parent directories, and warns on stderr if the
path is unwritable instead of losing the log silently.

`--verbose` adds one line per resolved link, queued file, duplicate and filter
decision — useful when the file count is not what you expected:

```
[2026-08-03 23:59:47] Resolved: [direct] https://host/x.jpg -> 1 file(s)
[2026-08-03 23:59:47] Queued: x.jpg <- https://host/x.jpg
[2026-08-03 23:59:47] Filtered: Excluded by --ignore/--include: y.mp4
```

Follow a running download from another terminal with `tail -f session.log`.

### Session-health warnings

An expired login usually does **not** produce a 403 — the forum serves readable
posts with the media links stripped, which looks like an empty thread. Three
warnings distinguish that from a genuinely empty one:

| Warning | Meaning |
| --- | --- |
| `No media links` | Posts parsed, but none had a supported host link. |
| `All hosts unresolved` | Host links found, none produced a file. |
| `Many unresolved hosts` | Most links produced nothing — partial breakage. |

All three suggest re-exporting cookies and retrying with `--reset-cookies`.

## Tests

A local mock XenForo forum (`tests/mock_forum.py`) serves thread pages,
pagination and real binaries, so the suite runs offline:

```bash
python -m tests.test_e2e      # 30 checks — parsing, downloads, filters, resume
python tests/test_cookies.py  # 32 checks — cookies, 403/login walls, prompt
python tests/test_logging.py  # 35 checks — --log-file, --verbose, stale session
```

Covers parsing (title, posts, spoilers, quoted-link exclusion), byte-exact
downloads, resume, `--include`/`--ignore`/`--separate-posts`, `--dry-run`,
cookie handling and the session-health warnings.

## Project layout

```
downloader.py              single-URL CLI
main.py                    batch CLI (URLs.txt)
src/
├── config.py              paths, colors, enums, HOSTS table
├── http_client.py         requests session w/ retries + cookies
├── file_utils.py          sanitising, state sidecar, filters
├── resolvers.py           per-host URL -> direct media
├── parsers/
│   ├── thread_parser.py   XenForo thread/post parsing
│   └── host_parser.py     host matcher (parseHosts port)
├── downloaders/
│   ├── media_downloader.py   one file: stream, retry, progress
│   └── thread_downloader.py  orchestration
└── managers/
    ├── progress_manager.py   Overall + File progress panels
    ├── log_manager.py        Log Messages panel + session.log
    ├── summary_manager.py    result/reason counters
    └── live_manager.py       Rich Live composition
```

## Notes

Only download content you have the right to access. Respect each site's terms of
service and rate limits — `--workers` defaults to 3 deliberately.
