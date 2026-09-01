# BUIDL — Media Downloader

Aplicativo para analisar e baixar imagens, vídeos, áudios e arquivos publicados em
threads XenForo. O BUIDL possui interface gráfica para Windows, aplicativo Android,
CLI e modo batch, todos usando o mesmo núcleo Python de parsers e resolvers.

O projeto foi adaptado a partir do
[`build.user.js` do ForumPostDownloader](https://github.com/SkyCloudDev/ForumPostDownloader/blob/main/dist/build.user.js),
com interface própria, retomada de downloads, prévias, seleção de arquivos e
tratamento adicional para hosts que mudam seus links com frequência.

> Use o BUIDL somente para conteúdo que você tem autorização para acessar e
> baixar. Respeite os termos, limites e direitos aplicáveis a cada serviço.

## Baixar

A versão atual é a **v1.3.0**:

| Plataforma | Arquivo | Indicação |
| --- | --- | --- |
| Windows | [`buidl-gui.exe`](https://github.com/sujirobase-ctrl/buidl/releases/download/v1.3.0/buidl-gui.exe) | Interface gráfica — recomendado |
| Android | [`BUIDL-android.apk`](https://github.com/sujirobase-ctrl/buidl/releases/download/v1.3.0/BUIDL-android.apk) | Android 7+, arm64 ou x86_64 |
| Windows | [`BUIDL-Windows-portable.zip`](https://github.com/sujirobase-ctrl/buidl/releases/download/v1.3.0/BUIDL-Windows-portable.zip) | GUI, CLI e batch juntos |
| Windows | [`buidl-cli.exe`](https://github.com/sujirobase-ctrl/buidl/releases/download/v1.3.0/buidl-cli.exe) | Uma thread pela linha de comando |
| Windows | [`buidl-batch.exe`](https://github.com/sujirobase-ctrl/buidl/releases/download/v1.3.0/buidl-batch.exe) | Várias URLs de `URLs.txt` |

Veja todos os arquivos, notas e checksums em
[`Releases`](https://github.com/sujirobase-ctrl/buidl/releases/latest). Os arquivos
`SHA256SUMS*.txt` permitem confirmar a integridade do download.

## Principais recursos

- Download de threads completas, páginas específicas ou posts selecionados.
- Galeria para visualizar, pesquisar, filtrar e escolher o que será baixado.
- Miniaturas de imagens e prévia curta de vídeos; quando o host não permite a
  reprodução, o BUIDL mantém a capa ou mostra um cartão de vídeo.
- Cache da análise enquanto o programa permanece aberto: voltar à galeria não
  busca toda a thread novamente. O botão **Atualizar thread** força uma nova análise.
- Retomada de arquivos interrompidos e estado persistente por thread.
- Downloads simultâneos, tentativas automáticas, atraso configurável, conexão por
  partes e limite de velocidade.
- Opção de separar posts em pastas e preservar subpastas de álbuns.
- Detalhes de falhas sem contar erro de miniatura ou prévia como erro de download.
- Tema claro/escuro e interface Android adaptada a diferentes tamanhos de tela e fonte.

## Windows — interface gráfica

1. Baixe e abra `buidl-gui.exe`.
2. Cole a URL da thread.
3. Informe um `cookies.txt` caso o fórum exija login.
4. Escolha a pasta de destino e marque **Todas as páginas**, se necessário.
5. Use **Visualizar e escolher** para selecionar arquivos ou **Iniciar download**
   para baixar toda a fila.

Na galeria, a seleção começa vazia. É possível filtrar por imagens, vídeos,
áudios ou outros arquivos, pesquisar por nome/post/host e marcar todos os
resultados do filtro. A seleção, os filtros, a página atual e as miniaturas são
mantidos ao sair e voltar para a visualização durante a mesma sessão.

A prévia de vídeo do Windows reproduz um trecho reduzido, sem áudio, de até seis
segundos. Ela é apenas uma ajuda para escolher o arquivo: falhar ao gerar a prévia
não impede o download do vídeo original.

## Android

O APK funciona diretamente no aparelho e não depende de um computador.

- **Capturar cookies** abre o SimpCity em um navegador interno. Faça login e toque
  em **Pronto**, no canto superior direito, para salvar a sessão no armazenamento
  privado do aplicativo.
- **Escolher pasta de destino** usa o seletor seguro do Android. O aplicativo só
  recebe acesso à pasta autorizada.
- **Analisar e escolher** abre a galeria com filtros, miniaturas e seleção.
- A aba **Arquivos** permite abrir os downloads e exportar os arquivos armazenados
  na pasta interna do aplicativo.
- Downloads interrompidos podem continuar sem baixar novamente as partes já salvas.

O APK da release é uma compilação debug para instalação manual e requer Android
7 ou mais recente, com processador `arm64-v8a` ou `x86_64`. Alguns aparelhos não
permitem selecionar a raiz ou a pasta `Downloads`; nesse caso, crie uma subpasta
como `Download/BUIDL` ou `Documents/BUIDL`.

Mais detalhes: [`android/README.md`](android/README.md).

## Cookies e privacidade

Fóruns com login podem devolver páginas incompletas ou respostas `403` quando a
sessão expira. Capture/exporte os cookies novamente se a thread aparecer vazia ou
muitos hosts deixarem de resolver.

No Windows e na CLI, exporte os cookies no formato Netscape (`cookies.txt`) pelo
navegador em que você já está conectado. Na GUI, selecione esse arquivo no campo
de cookies; na CLI, use `--cookies`.

No Android, cookies capturados ficam no armazenamento privado do aplicativo e
não são incluídos no APK, nos downloads ou nas exportações. O BUIDL não possui
telemetria, conta própria ou servidor para receber cookies. Não publique seu
`cookies.txt`, logs de sessão ou arquivos `.fpd_state.json`.

## Linha de comando

### Instalação pelo código-fonte

Requer Python 3.10 ou mais recente.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No Linux ou macOS, ative o ambiente com `source .venv/bin/activate`.

### Uma thread

```powershell
python downloader.py "https://forum.example/threads/exemplo.12345/" --all-pages
```

### Várias threads

Crie `URLs.txt` na pasta atual, com uma URL por linha:

```text
# Linhas vazias e comentários são ignorados
https://forum.example/threads/primeira.111/
https://forum.example/threads/segunda.222/
```

Depois execute:

```powershell
python main.py --all-pages
```

### Opções úteis

| Opção | Função |
| --- | --- |
| `--custom-path <pasta>` | Salva em `<pasta>/Downloads`. |
| `--cookies <arquivo>` | Usa cookies Netscape em fóruns com login. |
| `--no-cookies` | Executa anonimamente e não solicita cookies. |
| `--reset-cookies` | Esquece o caminho de cookies salvo. |
| `--all-pages` | Analisa todas as páginas da thread. |
| `--max-pages <n>` | Limita páginas quando `--all-pages` não é usado. |
| `--post <id>` | Baixa somente um post; pode ser repetido. |
| `--include <texto>` | Inclui apenas nomes que contenham o texto. |
| `--ignore <texto>` | Ignora nomes que contenham o texto. |
| `--workers <n>` | Define downloads simultâneos; padrão: 3. |
| `--max-retries <n>` | Define tentativas por arquivo; padrão: 6. |
| `--delay <segundos>` | Aguarda antes de iniciar cada arquivo; padrão: 3. |
| `--connections <n>` | Usa partes paralelas quando o host aceita HTTP Range. |
| `--rate-limit <MB/s>` | Limita a velocidade total. |
| `--separate-posts` | Cria uma subpasta para cada post. |
| `--flat` | Não cria subpastas de álbuns. |
| `--dry-run` | Analisa e lista sem baixar. |
| `--disable-ui` | Usa logs simples, sem a interface Rich. |
| `--log-file <arquivo>` | Define o arquivo de log. |
| `--clean-part` | Apaga temporários `.part` incompletos ao terminar. |
| `-v`, `--verbose` | Registra resoluções, filtros e itens da fila. |

Use `python downloader.py --help` para consultar todas as opções da versão instalada.

## Pastas e retomada

Sem `--custom-path`, a CLI cria `Downloads` na pasta atual:

```text
Downloads/
└── Título da thread/
    ├── imagem.jpg
    ├── video.mp4
    └── .fpd_state.json
```

O arquivo `.fpd_state.json` registra resultados e permite ignorar itens já
concluídos. Temporários `.part` são preservados por padrão para continuar depois.
Apagar o estado força uma nova avaliação dos itens, portanto faça isso somente
quando realmente quiser repetir o download.

## Hosts

Os padrões de hosts ficam em [`src/config.py`](src/config.py), e os resolvers em
[`src/resolvers.py`](src/resolvers.py). Entre os serviços tratados estão Bunkr,
Cyberdrop, Pixeldrain, Gofile, Erome, Redgifs, Saint, Imgur, Postimages, Pixhost,
Imgbox, ImgBB, JPG Church, Pixl, ImageKiwi, ImageBam, ImageVenue, Coomer/Kemono,
Reddit, Twimg, Nitter, Filester e links diretos conhecidos.

Hosts podem mudar páginas, APIs e proteções sem aviso. Por isso, uma URL abrir no
navegador não garante que ela aceite a mesma requisição automatizada. Atualizações
dos resolvers são distribuídas em novas versões do BUIDL.

## Compilar e testar

### Testes Python

```powershell
python -m pip install -r requirements.txt pytest
python -m pytest tests --ignore=tests/test_e2e.py -q
```

### Executáveis Windows

```powershell
pyinstaller --clean --noconfirm buidl.spec
pyinstaller --clean --noconfirm buidl-batch.spec
pyinstaller --clean --noconfirm buidl-gui.spec
```

### APK Android

Com JDK 21, Android SDK 36 e Python disponíveis:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File android\build.ps1
```

O GitHub Actions testa o projeto e compila Windows e Android em ambientes limpos.
Pushes e pull requests geram artefatos temporários; uma tag `vX.Y.Z` que corresponda
à versão de `pyproject.toml` publica automaticamente uma nova release com checksums.

## Estrutura do projeto

```text
gui.py                         interface gráfica Windows
downloader.py                  CLI para uma URL
main.py                        CLI batch para URLs.txt
src/
├── config.py                  configuração e tabela de hosts
├── resolvers.py               resolução de links por host
├── preview.py                 análise e cache da galeria
├── video_preview.py           prévia de vídeo no Windows
├── parsers/                   parser de threads e links
├── downloaders/               downloads, retomada e limite de taxa
└── managers/                  progresso, logs e resumos
android/                       aplicativo Android nativo + núcleo Python
tests/                         testes offline e de integração
.github/workflows/build.yml    testes, builds e publicação de releases
```

## Limitações

- Cookies podem expirar e precisam ser capturados/exportados novamente.
- Arquivos removidos, limites de CDN, bloqueios regionais e mudanças dos hosts
  podem impedir downloads mesmo quando a thread ainda está acessível.
- Nem todo host permite miniatura ou prévia de vídeo.
- O APK não é uma versão assinada para publicação na Play Store.
- O BUIDL não contorna permissões de acesso: é necessário possuir uma sessão válida.

Relate problemas com o host, a mensagem de erro e uma URL de exemplo sem publicar
cookies ou outros dados privados.
