# Histórico do projeto `buidl` (ForumPostDownloader)

> Registro completo do trabalho feito desde a sessão original
> (`20260803_215011_a79201` — "Análise de arquivo html baixado"), que travou,
> até a sessão atual. Compilado manualmente para não perder o contexto.

Projeto: downloader de mídia de fóruns (estilo SimpCity / ForumPostDownloader).
Local: `C:\Users\isaac\Downloads\buidl`

---

## 1. Filtro de `.webp` / `.avif` (início da sessão travada)

- O usuário queria que o downloader **NÃO baixasse** `.webp`/`.avif`.
- Removidas as extensões de:
  - `IMAGE_EXTENSIONS` (`src/config.py`)
  - `CONTENT_TYPE_EXTENSIONS` (`src/config.py`)
  - `DIRECT_LINK_PATTERN` (`src/config.py`) — com lookahead pra `.avif` não
    casar parcialmente em `.avi`.
- Criado teste de regressão `tests/test_webp_not_filtered.py` (4 checks).
- Verificado ao vivo: thread `beamoriyurumo` caiu de 314 → 263 arquivos;
  os 51 `.webp` antigos foram apagados do disco. Suíte verde.

## 2. Teste real de download — `nene-nenechi890.933945`

- Baixada thread com 1449 arquivos, **0 falhas, 0 skip, 225 MB**, 34min.
- Hosts: `simp6.cuckcapital.cr`, `c2wi-b.cdn.cr`, `pixeldrain.com`.
- Usuário notou que **vídeos do turbo.cr** não estavam sendo contados →
  adicionado resolução de vídeos do `turbo.cr`.

## 3. Alinhamento de hosts com a lista canônica

- Fonte canônica: lista `@connect` do `build.user.js` do
  [ForumPostDownloader (SkyCloudDev)](https://github.com/SkyCloudDev/ForumPostDownloader/blob/main/dist/build.user.js).
- Adicionados resolvers / host-entries:
  - `goonbox.cr` (resolver `_resolve_goodbox`)
  - CDNs do SimpCity (`cuckcapital.cr`, `scdn.st`, `cache8.st`)
  - variantes de `bunkr`, `saint2`
  - `jpg.fish/.pet/.su`, `ibb.co`, `box.com`, `pomf2.lain.la`
  - `pornhub/spankbang/xvideos/rule34/noodlemagazine/pvvstream` (best-effort)
- Dúvida do usuário: "o fallback genérico conflita com hosts específicos?"
  Resposta: **não**. O `resolve()` só usa `_resolve_direct` quando nenhum
  padrão casa; se um resolver específico falha, faz `break` (não vaza HTML
  de erro como se fosse mídia).

## 4. Empacotamento — exe + wheel

- Gerado `buidl.exe` (19 MB, PyInstaller --onefile, Windows).
- Usuário queria acesso fácil em vários dispositivos (PC + Android/Termux)
  sem copiar a pasta toda → escolheu a **Opção 1 (wheel local)** em vez de
  publicar no PyPI.
- `pyproject.toml` corrigido (subpackages `src.downloaders/parsers/managers`
  não iam pro wheel) → wheel `buidl-0.1.0-py3-none-any.whl` (49 KB).
- Cookies: ficam no mesmo dir do exe ou passa `--cookies caminho`.
- No Termux o `pip install` do wheel falhou por causa do **`lxml`** (precisa
  de `libxml2`/`libxslt` no Android).

## 5. Erro do log no Termux (`spoiledsoftie.152625`)

- Log do usuário mostrou **22 falhas `HTTP 429`** vindas de `c3wi-b.cdn.cr`.
- Causa raiz: **rate-limit do CDN por IP**, não bug do `buidl`.
  - Disparado por `--workers 3 --connections 4` = 12 conexões paralelas.
  - `--rate-limit 8` limita **banda**, não volume de requisições → não protege.
  - Prova: os mesmos arquivos que deram 429 foram baixados minutos depois.
- Teste de reprodução: rodei o mesmo comando no PC → **não** replicou (o
  resume pulou 243 arquivos e o CDN "esfriou" horas depois).

## 6. Correções aplicadas (esta sessão)

### 6.1 Proteção contra 429 (`src/http_client.py` + `src/config.py`)

- `get()` agora faz **backoff exponencial específico pra 429**:
  - Se vier header `Retry-After` → respeita (cap 60s).
  - Se não vier (caso SimpCity) → dorme `5s → 25s` (`RATE_429_BACKOFF ** (attempt+1)`).
- `RATE_429_BACKOFF = 5.0` adicionado em `src/config.py`.
- Defaults mais conservadores:
  - `MAX_RETRIES` 5 → **6**
  - `INTER_FILE_DELAY` 2.0 → **3.0s**
- `src/downloaders/media_downloader.py`: loop de retry também reconhece 429
  e aplica o mesmo backoff longo.

### 6.2 Troca `lxml` → `html.parser` (sem dependência C)

- Trocado `BeautifulSoup(html, "lxml")` → `"html.parser"` em 4 lugares:
  - `src/http_client.py`
  - `src/resolvers.py`
  - `src/parsers/thread_parser.py`
  - `src/downloaders/thread_downloader.py`
- Removido `lxml>=5.2.0` de `requirements.txt` e `pyproject.toml`.
- **Por quê:** no Termux o `lxml` não compila (falta `libxml2`/`libxslt`);
  `html.parser` é puro Python, embutido, instala em qualquer lugar sem
  compilar nada. Funcionalmente idêntico pra este caso (seletores básicos).

### 6.3 Verificação

- Suíte: e2e 30, cookies 32, logging 35, chunked 6, webp 4, filester 3,
  goonbox 4, skip 3, bunkr 3 — **tudo verde**.
- Teste ad-hoc (mock do `HttpClient.get` recebendo 429):
  - 429 sem `Retry-After` → 30.0s (backoff longo) ✓
  - 429 com `Retry-After:2` → 4.0s (header respeitado) ✓
  - 500 → 3.0s (backoff curto) ✓
- Wheel instalado num venv **sem lxml** → `buidl --help` exit 0 ✓

## 7. Download real final (`spoiledsoftie.152625`)

Comando:
```bat
python downloader.py "https://simpcity.cr/threads/spoiledsoftie.152625/" ^
  --all-pages --cookies "Downloads/cookies.txt" ^
  --workers 3 --connections 4 --rate-limit 8 --disable-ui
```

Resultado:
```
Completed: 1047 | Skipped: 243 (já baixado) | Failed: 0
Tempo: 51min09s
```
- 1047 baixados do zero + 243 pulados (resume dos do Termux) = **1290 na pasta**.
- **0 erros 429** — os arquivos que falhavam no celular baixaram limpos.

Pasta de saída:
```
C:\Users\isaac\Downloads\buidl\Downloads\Request Patreon Fansly SpoiledSoftie\
```

## 8. Entregáveis finais (`C:\Users\isaac\Downloads\buidl\dist\`)

| Arquivo | Tamanho | Uso |
|---|---|---|
| `buidl.exe` | 19 MB | Windows, sem Python |
| `buidl-0.1.0-py3-none-any.whl` | 50 KB | `pip install` em qualquer SO/Python 3.10+ (sem lxml) |

### Instalação no Termux (agora sem o pepino do lxml)
```bash
pip install buidl-0.1.0-py3-none-any.whl
# puxa só requests / beautifulsoup4 / rich — NÃO precisa de pkg install libxml2
buidl "URL_DA_THREAD" --all-pages --cookies cookies.txt
```

> **`--workers` / `--connections` NÃO são obrigatórios** (têm default 3/1).
> O comando acima já funciona. Só use valores conservadores se quiser minimizar
> 429 de cara — o backoff automático (seção 6.1) já cobre o resto:
> ```bash
> buidl "URL_DA_THREAD" --all-pages --cookies cookies.txt --workers 2 --connections 2
> ```

### Uso no PC (wheel)
```bat
pip install C:\Users\isaac\Downloads\buidl\dist\buidl-0.1.0-py3-none-any.whl
buidl "URL_DA_THREAD" --all-pages --cookies cookies.txt
```

## 9. Lições / notas
- `--rate-limit N` não protege contra 429 (controla banda, não requisições).
- Pra evitar 429: reduzir paralelismo (`--workers 1 --connections 2`) ou
  confiar no backoff automático agora implementado.
- `html.parser` substitui `lxml` sem perda de funcionalidade neste projeto.

## 10. Estrutura de pastas `Photos/` + `Videos/` (nova feature)

Pedido do usuário: ao baixar, separar imagens em `Photos/` e vídeos em
`Videos/` **dentro da pasta da thread**. Regra: `Photos/` sempre criada se
houver imagens; `Videos/` só se houver vídeos (senão fica só `Photos/`).

Implementação (`src/downloaders/media_downloader.py`, `download()`):
```python
folder = destination_folder
if media.subfolder:
    folder = folder / sanitize_name(media.subfolder)
# Categoria por tipo de arquivo:
_ext = Path(media.filename or media.url).suffix.lower()
category = "Videos" if _ext in VIDEO_EXTENSIONS else "Photos"
folder = folder / category
# folder.mkdir só acontece ao gravar -> Videos/ aparece só se houver vídeo
```
- Usa `VIDEO_EXTENSIONS` de `src/config.py` (mesma lista do resto do código).
- `Videos/` é criado **condicionalmente** porque `mkdir` roda no momento do
  write — se não houver vídeo, a pasta simplesmente não existe.
- Não quebra o `resume` (por URL): arquivos já baixados na raiz da thread
  antiga continuam lá; o buidl não os move, só novos downloads vão pra
  `Photos/`/`Videos/`.

Testes:
- `tests/test_e2e.py` ajustado: `test_download` agora espera
  `folder/Photos/photo1.jpg` e `folder/Videos/clip.mp4` (30/30 verde).
- Teste ad-hoc (mockando `_attempt`): imagem→`Photos/`, vídeo→`Videos/`,
  ambas pastas criadas fisicamente (5/5 PASS).

Reorganizar downloads antigos (que ficaram na raiz):
```bash
# Na pasta da thread, mover imagens pra Photos/ e vídeos pra Videos/
cd "Request Patreon Fansly SpoiledSoftie"
mkdir -p Photos Videos
for f in *.*; do
  case "${f##*.}" in
    jpg|jpeg|png|gif|webp|avif|bmp) mv "$f" Photos/ ;;
    mp4|mkv|mov|webm|avi|m4v)       mv "$f" Videos/ ;;
  esac
done
```

---

## 11. Feature `Audio/` (categoria de áudio separada)

Pedido do usuário (thread ikumi-asmr.85869): *"quando qualquer tipo de audio
criar uma pasta audio e dentro coloca qualquer tipo de audio baixado"*.

### O que mudou
Três baldes de categorização em `src/downloaders/media_downloader.py`
(`download()` ~linha 71-82), por extensão do arquivo:
- `Audio/`  → `AUDIO_EXTENSIONS` (.mp3 .wav .ogg .oga .m4a .aac .flac
  .opus .wma .aiff .aif .caf .weba)
- `Videos/` → `VIDEO_EXTENSIONS`
- `Photos/` → tudo o resto (imagens)

A pasta só é criada fisicamente quando há arquivo daquele tipo (regra
condicional: `Videos/` só aparece se houver vídeo; `Audio/` só se houver áudio).

### Por que áudio "não baixava antes" — na verdade baixava, só misturado
No código antigo a lógica era `Videos if ext in VIDEO else Photos`. Então
`.mp3`/`.wav` caíam no `else` → iam parar em `Photos/`. No log do Termux da
Ikumi os 43 completos **incluem os mp3/wav** — eles baixaram, só ficaram
misturados em `Photos/`. A nova feature isola em `Audio/`.

### 2 correções de suporte que eram necessárias
- `src/config.py`: `DIRECT_LINK_PATTERN` (regex de link direto) não listava
  áudio → adicionado `mp3|wav|ogg|m4a|flac|aac|opus` (mais `webp`).
- `src/resolvers.py`: `MEDIA_EXTENSIONS` (usado por `is_direct_media()`) era
  `IMAGE + VIDEO + ARCHIVE` → passou a incluir `AUDIO_EXTENSIONS`. Sem isso o
  parser descartava links `.mp3` diretos.

### Testes
- `tests/mock_forum.py`: fixture `track.mp3` + link no post 1 + content-type
  `audio/mpeg`.
- `tests/test_e2e.py`: `EXPECTED_SIZES` agora tem `track.mp3`; `test_download`
  roteia por `AUDIO_EXTENSIONS`→`Audio`; `test_resume` espera 6 skips;
  `test_parser` espera 4 links.
- Suíte: **32/32 green**. Ad-hoc verify (download real no mock): `.mp3`
  escrito em `Audio/track.mp3` (size 5003) → **PASS**.

### PEGADINHA DO RESUME (importante)
O `buidl` salva `.fpd_state.json` **dentro da pasta da thread** (ex:
`Downloads/Request Patreon Twitch Ikumi (ASMR)/.fpd_state.json`), registrando
cada URL como `"completed"`/`"failed"`. Na re-run, `thread_downloader.py`
linha ~339 pula quem está `"completed"`.

Consequência na Ikumi (já baixada com código VELHO):
- Os 43 (incl. mp3/wav) estão marcados `completed` → **pulados** no re-download.
- Os 52 vídeos que deram 403 (`fsc1/2/3.cdn.cr` — bloqueio do servidor, não
  erro de rede) estão `failed` → **retentados e 403 de novo**.
- Resultado prático de re-rodar: `Completed: 0 | Skipped: 43 | Failed: 52`
  → **zero arquivo novo**.
- **O `Audio/` NÃO aparece na Ikumi re-rodando**, porque tudo já está
  `completed`: o código novo não tem nada pra baixar, e a pasta `Audio/` não é
  criada. Os mp3s antigos continuam em `Photos/`. `Audio/` só surge em
  **threads baixadas com o código novo**.

### Como aplicar no Termux
1. Copiar `dist/buidl-0.1.0-py3-none-any.whl` pro device e:
   `pip install --force-reinstall buidl-0.1.0-py3-none-any.whl`
2. Rodar sempre de `us/` (onde está `cookies.txt`), não de `us/Downloads/`,
   senão o `download_root` aninha `Downloads/Downloads/`.
3. Antes de re-rodar uma thread: `ls -a "nome da thread/"` e checar
   `.fpd_state.json`. Dry-run confirma o skip:
   `python -m downloader "<url>" --all-pages --cookies cookies.txt \
    --workers 1 --connections 1 --disable-ui --dry-run`
   Se mostrar `Skipped: N (Already downloaded)`, o estado foi lido.
4. Pra deixar a Ikumi consistente (áudio em `Audio/`), reorganizar os mp3/wav
   já-baixados com script que move (não apaga) — decidido como Opção B,
   ainda não escrito.

---

*Gerado em 2026-08-05 — consolidação pós-sessão-travada (seções 1-10) +
features Audio/ (seção 11), UI/erro (seção 12), .part (seção 13) e UI-fundão
(seção 14).*

---

## 14. Correção de fundo do layout (segunda passada — draw path único)

Após a seção 12 (`screen=True` + lock + fallback), o usuário voltou pedindo
"corrija a ui". Investigação: o exe que ele logou o empilhamento era o de
01:30 (sem `screen=True`); o de 20:03 (pós-seção 12) já não empilha — provado
por teste de render com `Console(record=True)`: o snippet mostra **um único**
conjunto de painéis (Overall + File lado a lado) atualizando a %, não dezenas
empilhados.

Mas havia ainda uma causa raiz latente: `update_log()` chamava
`self.live.update()` **além** do `auto_refresh=True` do `Live`. Eram DOIS
caminhos de desenho; em rajadas de eventos dos workers isso intercala writes
ANSI e é exatamente o que duplica/empilha painéis. Correção definitiva:

- `update_log()` **não chama mais `live.update()`** — só atualiza a
  `logger_table` (e o arquivo de log). O `Live(auto_refresh=True)` repinta o
  frame inteiro (progress + log + footer) no seu tick fixo (10/s). Um único
  caminho de desenho → impossível empilhar.
- `stop()` agora faz `live.refresh()` (repintura atômica do frame final com
  "Script ended" + resumo) ANTES de `live.stop()`, pra garantir que o resumo
  apareça no alternate-screen antes de sair; depois `console.print()` congela
  o frame na tela normal (já fazia).
- `_started`/`_live_lock` mantidos (lock usado no `stop()`).

### Teste de render (evidência real, não só suíte verde)
`hermes-verify-render.py` (temp, deletado): instancia `LiveManager` com
`Console(force_terminal=True, record=True)`, dispara 4 threads de worker
chamando `update_log`/`update_task` concorrentes, e inspeciona
`export_text()`:
- `no exceptions during concurrent live updates` ✓
- `panel sets bounded (no stack)` ✓ (≤6 ocorrências de "Overall Progress",
  não dezenas)
- `summary present in render` ✓

### e2e
`tests/test_e2e.py` (main()): **32/32 PASS** após a mudança.

### Build
Reconstruído `dist/buidl-0.1.0-py3-none-any.whl` e `dist/buidl.exe` (21:04),
ambos com a correção. Próximo teste do usuário deve usar este exe.

### Nota sobre o fallback
Se o terminal reportar `is_terminal=False` (stdout redirecionado / wrapper sem
tty), o buidl cai em `--disable-ui` automático (print linha-a-linha, sem
painéis) — não empilha, mas perde o layout. Em cmd/PowerShell reais e no
Termux (tty de verdade) o layout aparece.

---

## 13. Arquivos `.part` incompletos — aviso + `--clean-part`

O usuário achou 5 arquivos `.mp4.part` (29–81 MB) na pasta da Ikumi e não os
viu no filtro. Causa: são downloads **interrompidos** por erro de rede — o
`media_downloader` escreve num temp `nome.ext.part` e só renomeia pra final
quando chega a 100% (`temp_path.replace(target)`). Os 5 `.part` caíram (hosts
bunkr/prxp instáveis) e ficaram pela pasta. No `.fpd_state.json` eles estão
`"failed"` (não `completed`), então o resume **retoma do que já baixou**
(`resume_pos = temp_path.stat().st_size`).

O buidl **não filtrava nem avisava** sobre `.part` — daí parecer "filtro
perdido". Decisão: implementar a Opção 2 (melhor custo/benefício): avisar
sempre + `--clean-part` pra apagar, em vez de só re-rodar (deixa lixo) ou
apagar (perde bytes retomáveis).

### Mudanças
- `downloader.py`: novo arg `--clean-part` (store_true) + passado em
  `options_from_args` via `getattr(args, "clean_part", False)` (default False
  pra não quebrar callers que montam o namespace na mão).
- `src/downloaders/thread_downloader.py`:
  - `ThreadOptions.clean_part: bool = False`.
  - `download_thread()` agora guarda o retorno de `_run_downloads` e chama
    `_report_leftover_parts(root)` antes de retornar.
  - `_report_leftover_parts()`: varre `root.rglob("*.part")`. Se houver:
    - modo normal → log `Incomplete files left: N file(s) (X MB) are
      incomplete .part downloads interrupted by a network error...`;
    - `--clean-part` → apaga os `.part` (try/except OSError) e loga
      `Cleaned .part: Removed K/N incomplete temp file(s) (X MB)...`.
    - ignorado em `dry_run`. Arquivos finalizados (`*.mp4` sem `.part`) nunca
      são tocados.

### Testes
- Ad-hoc `hermes-verify-part.py` (temp, deletado): 7/7 PASS — aviso mantém
  `.part` + arquivos reais; `--clean-part` apaga `.part` e mantém reais; sem
  `.part` fica silencioso.
- `tests/test_e2e.py` (main()): **32/32 PASS** após a mudança.

### Build
Reconstruído `dist/buidl-0.1.0-py3-none-any.whl` e `dist/buidl.exe` (ambos com
a feature).

### Uso prático na Ikumi
Rodar do mesmo diretório (`dist/`) com `--clean-part` apaga os 5 `.part`
órfaos; sem `--clean-part` ele avisa e eles são retomados no próximo run.

---

## 12. Correção do layout (painéis empilhados) + resumo de erro legível

Reportado pelo usuário: ao rodar `buidl.exe` (PC) e `python -m downloader`
(Termux) o Rich `Live` desenhava **dezenas de painéis "Overall Progress" /
"File Progress" empilhados** verticalmente, em vez de um painel fixo que
atualiza no lugar. Também: a mensagem de erro de download era ilegível
(URL gigante + stack do requests inteira numa linha só).

### Causa do empilhamento
O `Live` era criado sem `screen=True` e sem serialização. Dois fatores
faziam o Rich "vazar" frames:
1. Conteúdo de altura variável (nomes de arquivo longos quebram linha no
   painel de log) → o Rich não apaga o frame anterior direito e empilha.
2. `update_log()` chamava `live.update()` a partir das threads dos workers
   (ThreadPoolExecutor) em concorrência com o tick de refresh do próprio
   `Live` → escritas ANSI intercaladas corrompem o render.

### Correção (`src/managers/live_manager.py`)
- `Live(..., screen=True, auto_refresh=True, redirect_stderr=True,
  console=Console(highlight=False))`. `screen=True` usa o alternate-screen
  buffer → cada frame substitui o anterior por inteiro, sem vazar linhas,
  independente de altura variável.
- `self._live_lock = threading.Lock()` e todo `live.update()` roda dentro do
  lock → workers e refresh thread não intercalam.
- `self._started` guard: `update_log()` não desenha antes de `live.start()`
  (antes o "Script started" era desenhado solto, fora do live).
- Fallback: se `Console().is_terminal` for False (stdout redirecionado /
  wrapper sem tty), `disable_ui` vira True automaticamente → cai no modo
  print linha-a-linha (sem empilhar). No cmd real e no Termux (tty de verdade)
  o layout bonito aparece.
- `stop()` re-imprime o frame final com `console.print()` APÓS `live.stop()`,
  porque `screen=True` destrói o alternate-screen ao sair — assim o resumo
  final (Completed/Skipped/Failed + tempo) continua visível na tela normal.

### Resumo de erro legível (`src/error_summary.py` + `media_downloader.py`)
Novo módulo `summarize_error(raw)` colapsa a exception crua numa linha PT-BR:
- `timeout` → "timeout de conexão — host lento ou fora do ar"
- `No address associated with hostname` → "DNS falhou — domínio offline"
- `403` → "bloqueado pelo servidor (403) — link expirado ou acesso negado"
- `429` → "rate-limit (429) — aguarde alguns minutos e tente de novo"
- `404` → "arquivo não encontrado (404) — link quebrado"
- `5xx` → "erro temporário do servidor (5xx)"
- HTML no lugar do arquivo → "servidor respondeu com página HTML (login expirado)"
- Hints por host: `prxp-b.cdn.cr`/`bunkr` → "host do bunkr parece
  instável/offline"; `fsc` → "CDN do SimpCity barrou este link (403)"; etc.
O `media_downloader.download()` agora loga `summarize_error(last_error)` no
evento "Download failed" (o `message` completo ainda vai pro state/arquivo de
log, só a tela mostra o resumo).

### Testes
- `tests/test_e2e.py` (main() com servidor mock): **32/32 PASS** após as
  mudanças (Audio/, resume, parser, filters, dry-run intactos).
- Validação manual de `summarize_error` com 6 casos reais → saídas corretas.

### Build
Reconstruído `dist/buidl-0.1.0-py3-none-any.whl` e `dist/buidl.exe` (ambos
incluem `error_summary.py` e o `live_manager` corrigido).
