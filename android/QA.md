# Verificação local — 30/08/2026

## Atualização 1.3.0 — interface e acessibilidade

Artefato: [buidl-android-1.3.0-debug.apk](../Arquivo-BUIDL/Distribuicoes/Android/dist-android-1.3.0/buidl-android-1.3.0-debug.apk) (38.951.058 bytes).
Pacote: `com.sujirobase.buidl`, versão `1.3.0-mobile`, código 4.
SHA-256: `fa0b679fb533f07aa7f954e615c5cc94da6d91bd733fdb0f9c602d474497d378`.

- Interface nativa renovada: temas claro/escuro/sistema, ícones vetoriais
  desenhados em código, link e ações prioritários, opções avançadas recolhíveis,
  busca/filtros recolhíveis, resumo compacto e estados vazios orientados.
- A tela de cookies compartilha os temas e controles, conservando HTTPS,
  restrição de domínio, ausência de ponte JavaScript, cookies HttpOnly e
  proteção de screenshots. Nenhum resolver ou código de download foi alterado
  nesta atualização de interface. EXEs Windows não foram recompilados.
- **107 testes Python passaram** (36,93 s), sem o teste E2E de rede externa.
- **UiTest passou** nos temas claro e escuro, com a galeria de seis arquivos:
  retrato 100%, retrato 200%, paisagem 200% e paisagem 100%. A rodada final
  confirma a orientação e `fontScale` realmente recebidas pela Activity.
  Verifica contraste de texto >=4,5:1, contorno de campo >=3:1, alvos >=48 dp,
  associação labelFor, ausência de nomes técnicos falados, texto sem corte
  vertical/reticências, aba selecionada e formulário preservado após recriar.
- **CookieCaptureTest + SmokeTest#fullWorkflow passaram** (15,774 s): cookies
  fictícios em página offline, seleção/cache/retomada, MP4 nativo, capa de fallback
  e uma falha esperada para HTML no lugar do arquivo. O último ajuste posterior
  foi somente a cor de fundo do estado desabilitado dos botões; a matriz UiTest
  foi repetida depois dele.
- **DestinationTest passou** (14,26 s) após escolher a pasta pelo seletor real:
  colisão preservada, gravação automática, seleção, retomada, listagem, reinício
  e erro explícito após revogar apenas a permissão QA.
- O botão **Aparência → Claro** foi acionado pela interface real via ADB, assim
  como **Escolher pasta → Nova pasta → Usar esta pasta → Permitir**.
- Capturas revisadas em `android/qa/ui-*.png`; mídia apenas artificial. A pasta
  externa de teste foi copiada para `android/qa/destination-export-backup-ui-1.3.0`
  antes da limpeza. Não foram lidos cookies pessoais nem testado login real.
- O APK possui assinatura v2 verificada e ABIs arm64-v8a/x86_64.
- Instalado no MuMu com `adb install -r` e versão 1.3.0-mobile confirmada, sem
  limpar dados ou desinstalar o aplicativo principal. Fonte 1.0 e rotação
  automática originais restauradas. Pacotes QA, servidor 8876 e pasta externa
  fictícia removidos; o backup local de seis amostras foi mantido.

### Ajustes no próprio teste

As capturas iniciais ocorreram durante a animação da Activity; passou-se a
aguardar o compositor antes de capturar. Uma verificação de altura inicialmente
considerava a linha vazia de um botão apenas com ícone como texto cortado;
agora mede texto não vazio. A rotação solicitada por settings nem sempre era
aplicada pelo MuMu durante instrumentação: UiTest passou a usar a rotação da
UiAutomation e a afirmar orientação/fontScale, liberando a rotação ao terminar.
Na repetição do smoke, um argumento com espaços não chegou corretamente ao
Android e a limpeza não rodou; o teste então encontrou o download anterior e
contou-o como ignorado. Corrigida a passagem do argumento, a limpeza restrita à
amostra e o fluxo completo passaram novamente.

**Limites:** validação automática de semântica e revisão visual não substituem
teste auditivo com TalkBack. Não foram testados aparelhos físicos, todos os
fabricantes/tamanhos de tela ou todos os hosts. APK de instalação manual/debug.

## Atualização 1.2.0 — escolha da pasta de destino

Artefato: [buidl-android-1.2.0-debug.apk](../Arquivo-BUIDL/Distribuicoes/Android/dist-android-1.2.0/buidl-android-1.2.0-debug.apk) (38.878.369 bytes).
Pacote: `com.sujirobase.buidl`, versão `1.2.0-mobile`, código 3.
SHA-256: `f6225c73f2c44d3721268f166e0234fb7277509ed92771155d2248cbf03da1e5`.

- **107 testes Python passaram**, incluindo 24 do adaptador móvel. Foram
  acrescentados testes de entrega no destino, retomada/reinício, troca de pasta
  sem nova análise, cópia pendente reutilizada após falha, perda de permissão,
  arquivo removido, colisão de nome e falha de persistência do recibo.
- **DestinationTest passou no MuMu** (`OK (1 test)`, 13,803 s), com a pasta
  `Documents/BUIDL-DEST-QA-7f31a9` selecionada pela interface real do Android:
  - Seletor → Nova pasta → Usar esta pasta → Permitir → destino exibido no app.
  - Arquivo artificial `photo2.jpg` preexistente preservado byte a byte; a imagem
    baixada recebeu um sufixo, sem sobrescrever esse arquivo.
  - Download seletivo, seleção após recriar Activity e retomada sem nova busca.
  - Cinco downloads válidos gravados automaticamente na pasta; HTML servido
    como vídeo resultou na única falha prevista, sem falso sucesso.
  - Lista Arquivos mostrou URIs SAF; tamanhos e conteúdo dos arquivos foram lidos
    novamente pelo ContentResolver. Temporário da imagem concluída foi removido.
  - Novo Engine recuperou destino e cinco recibos de arquivos concluídos.
  - Permissão da variante QA revogada: a próxima tentativa mostrou erro e
    manteve o destino, sem gravar silenciosamente na pasta interna.
- **CookieCaptureTest e SmokeTest#fullWorkflow passaram novamente** juntos
  (`OK (2 tests)`, 17,441 s), validando cookies, downloads, cache e prévias na
  pasta padrão após as alterações do mecanismo de finalização.
- A captura de cookies real do usuário não foi acessada pelos testes. Os testes
  rodaram no pacote separado `com.sujirobase.buidl.qa`, usando somente mídia e
  cookies artificiais. A permissão revogada foi apenas a desse pacote QA.
- APK final com assinatura v2 verificada, ABIs arm64-v8a/x86_64; atualizado com
  `adb install -r`, sem desinstalar ou limpar dados do BUIDL principal.
- Os seis arquivos artificiais (incluindo o arquivo de colisão) foram copiados
  para `android/qa/destination-export-backup-7f31a9`, antes da remoção da pasta de
  testes no MuMu. Auxiliares QA, servidor HTTP e reverse ADB 8876 foram removidos.

**Limites:** validado o provedor de armazenamento local do MuMu/Android 15, não
cartão SD, todos os provedores de nuvem, discos cheios reais ou encerramento
abrupto durante cada ponto de gravação. Falta de espaço e erro de recibo foram
simulados nos testes Python. É necessário espaço temporário no aparelho.

## Atualização 1.1.0 — captura de cookies

Artefato: [buidl-android-1.1.0-debug.apk](../Arquivo-BUIDL/Distribuicoes/Android/dist-android-1.1.0/buidl-android-1.1.0-debug.apk) (39.015.185 bytes).
Pacote: `com.sujirobase.buidl`, versão `1.1.0-mobile`, código 2.
SHA-256: `c3d760e5ce83a8c855e5be5e6564cad25451438e81aebe895ea48d1aa838d46d`.

- **101 testes Python passaram**, incluindo 18 do adaptador móvel. Captura:
  persistência de cookies/identificação do WebView, cookie HTTPS ausente em HTTP
  ou hosts externos, duplicatas, limites, entradas inválidas, erro ao substituir
  o arquivo, preservação da sessão anterior, importação manual e remoção.
- Ruff (`--select E9,F,I`) passou nos dois módulos Python alterados. A seleção
  completa ainda inclui avisos de estilo preexistentes no adaptador.
- **Dois testes instrumentados passaram juntos no MuMu** (`OK (2 tests)`, 16,26 s),
  usando o pacote isolado `com.sujirobase.buidl.qa`:
  - `CookieCaptureTest`: botão principal abre a Activity interna; botão Pronto;
    captura vazia mantém tela aberta; cookie fictício HttpOnly capturado pela API
    nativa; novo Engine Python reutiliza sessão e User-Agent; origem validada;
    voltar/captura vazia preserva arquivo anterior.
  - `SmokeTest#fullWorkflow`: análise de duas páginas, seleção, cache entre abas,
    recriação da Activity, retomada, reprodução MP4, capa de fallback e contagem
    correta de falhas, com cinco arquivos artificiais válidos ao final.
- A captura de teste é offline: o fixture existe somente na variante QA e
  bloqueia requisições de rede. Não está no APK normal. Nenhum cookie fictício
  foi enviado ao SimpCity, e o teste não acessou cookies da instalação normal.
- O primeiro teste de regressão parou na permissão de notificações da variante
  recém-instalada; o auxiliar agora concede a permissão apenas à variante QA.
  Também passou a aguardar a atualização do estado após remover os cookies
  fictícios, evitando ler uma snapshot antiga no teste seguinte.
- APK final com assinatura v2 verificada, ABIs arm64-v8a/x86_64; instalado com
  `adb install -r`, sem desinstalar nem limpar os dados do BUIDL principal.
- No APK normal, a página real `https://simpcity.cr/` e o formulário **Log in**
  carregaram no WebView do MuMu (110.0.5481.154.1), com Pronto no canto superior
  direito. Não houve preenchimento de credenciais nem captura da sessão real.
  O formulário ficou aberto para o usuário efetuar seu próprio login.
- Os dois pacotes auxiliares QA e suas mídias artificiais foram removidos. O
  servidor local foi encerrado e o redirecionamento ADB 8876 foi removido.

**Limite:** login de uma conta real e aceitação desses cookies pelo site não
foram testados. O servidor pode expirar sessões ou recusar o cliente Python
mesmo com o mesmo User-Agent. Não há promessa de contornar bloqueios dos hosts.

## Histórico: versão 1.0.0

Artefato: [buidl-android-1.0.0-debug.apk](../Arquivo-BUIDL/Distribuicoes/Android/dist-android-1.0.0/buidl-android-1.0.0-debug.apk) (38.979.304 bytes).
Pacote: `com.sujirobase.buidl`, versão `1.0.0-mobile`, código 1.
SHA-256: `912e370a951f1853cd107fa233cd374530622ede4a7867410424f3230ff76e01`.

## Resultados

- **86 testes Python passaram**, incluindo regressões do downloader Windows e
  testes específicos do adaptador Android. Ruff passou nos novos módulos Python.
- **Teste instrumentado no MuMu passou** (`SmokeTest#fullWorkflow`), com Android
  15, ABI x86_64, usando o APK instalado por ADB e um servidor HTTP local.
  - Análise de duas páginas e seis arquivos artificiais.
  - Download somente da segunda imagem selecionada.
  - Seleção mantida entre abas e após recriação da Activity.
  - Reabertura sem nova análise; retomada ignorando o arquivo concluído.
  - Reprodução real de MP4 pelo MediaPlayer Android, sem áudio.
  - HTML no lugar do vídeo aciona a capa e não aumenta as falhas de download.
  - Download completo: quatro novos arquivos, um ignorado e uma falha prevista;
    cinco arquivos válidos no armazenamento final.
- **Exportação SAF testada pela interface Android**: cinco arquivos copiados
  para uma pasta nova selecionada no gerenciador de documentos.
- **Importação de cookies testada pela interface Android**, com um cookie
  fictício de `qa.invalid`. O cookie foi removido em seguida; nenhum cookie real
  foi usado.
- Compilação final instalada e aberta no MuMu. Assinatura APK v2 verificada por
  `apksigner`; ABIs arm64-v8a e x86_64 confirmadas por `aapt`.
- As mídias e a URL de teste foram removidas do aplicativo com uma rotina que
  valida a pasta, os nomes e os tamanhos antes de excluir. A cópia exportada tem
  backup local em `android/qa/export-backup`. O auxiliar de testes foi removido e
  a rotação automática do MuMu foi restaurada.

## Escopo e limites

Estes testes não validam todos os hosts reais, cookies pessoais, aparelhos ARM
físicos, encerramento pelo fabricante durante horas em segundo plano ou todos os
provedores SAF. O APK é de teste/debug, não uma publicação na Play Store.

O MuMu ocasionalmente encerra `uiautomator dump` com código 135/139 depois de
escrever o XML com sucesso. O utilitário ADB só aceita esse caso quando a saída
confirma que o dump foi salvo; não trata falhas genéricas como sucesso. Os testes
instrumentados não dependeram desse workaround para validar o fluxo funcional.

Capturas de evidência ficam em `android/qa/qa-gallery.png`, `qa-video.png`,
`qa-video-fallback.png` e `qa-failures.png` (somente conteúdo artificial).
