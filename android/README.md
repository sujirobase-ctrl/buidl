# BUIDL Android — 1.5.2-mobile

Aplicativo Android nativo (Java) com o downloader Python do projeto embutido via
[Chaquopy](https://chaquo.com/chaquopy/doc/current/android.html). Não depende do PC
para funcionar: a análise e os downloads acontecem no aparelho. A interface Tk do
Windows não foi incluída nem alterada.

## Uso

1. Instale o APK e abra **BUIDL**.
2. Ao tocar em **Baixar tudo**, **Baixar filtro** ou **Selecionados**, escolha ou
   crie a pasta e confirme **Usar esta pasta → Permitir**. O seletor é aberto em
   toda nova tentativa de download; não há destino interno silencioso.
3. Em **Baixar → Capturar cookies**, faça login no SimpCity dentro do aplicativo
   e toque em **Pronto**, no canto superior direito. Cole a URL da thread em
   **Baixar**. A importação de `cookies.txt` Netscape continua disponível.
4. Use **Analisar e escolher**. Na **Galeria**, marque os arquivos e toque em
   **Baixar selecionados**. Com fonte normal em retrato, o botão permanece fixo.
   Com fonte ampliada/tela baixa, ele fica no início da área rolável; em telas
   largas, no painel lateral de atividade.
5. **Buscar e filtrar** expande a busca e o tipo de arquivo. **Baixar resultados
   do filtro** baixa imediatamente tudo que corresponde à busca e ao tipo atuais.
   **Opções**, na galeria, permite marcar/desmarcar o filtro, baixar todos ou
   atualizar a thread. Trocar de aba não repete a análise.
6. Em **Arquivos**, abra os downloads do último destino usado. Se um nome já
   existir, o provedor de arquivos pode criar outro nome para evitar a substituição.

O app inclui busca, filtros por tipo, paginação, miniaturas, prévia de vídeo sem
áudio, seleção preservada durante a sessão, retomada de arquivos, notificações,
progresso e detalhes de falhas. Os resolvers são os mesmos de `../src`.

### Visual e acessibilidade

- O botão de paleta, no canto superior direito, abre **Aparência**: Automático
  (sistema), Claro ou Escuro. A escolha é lembrada e não perde a URL, a seleção
  ou a galeria em memória. O padrão inicial continua escuro.
- Link e ações principais aparecem primeiro. Filtros de extensão, separação por
  post e quantidade simultânea ficam em **Opções avançadas**.
- Abas com ícones e indicação de seleção; cartões e tipografia consistentes;
  atividade compacta após concluir para sobrar espaço para as prévias.
- Controles com alvos de toque de pelo menos 48 dp, campos com rótulos
  persistentes associados, títulos semânticos e descrições contextualizadas
  para abrir cada arquivo. IDs técnicos não são mais nomes falados.
- Texto usa sp e pode crescer; testado a 100% e 200% em retrato/paisagem no
  MuMu. Painéis e diálogos são roláveis quando necessário. A URL é um campo de
  linha única com rolagem horizontal, não uma indicação de link truncado.
- Paletas verificadas para contraste de texto de pelo menos 4,5:1 e contorno
  dos campos de pelo menos 3:1. Referência:
  [acessibilidade em Views Android](https://developer.android.com/guide/topics/ui/accessibility/views/apps-views).
- A tela de captura de cookies acompanha o tema, mantém **Pronto** no topo à
  direita e conserva as proteções de navegação/captura da versão anterior.
- Não houve teste auditivo manual com TalkBack ou com aparelhos físicos nesta
  rodada; os testes verificam semântica nativa, geometria, contraste e layout.

### Pasta de destino

- Os arquivos são salvos na pasta escolhida para aquela tentativa, organizados
  por thread e categoria. O app sempre pergunta o destino antes de baixar.
- A gravação usa o Storage Access Framework: o app acessa somente a árvore
  autorizada pelo seletor Android, sem pedir acesso geral ao armazenamento.
- Cada arquivo baixa para um temporário no app, para manter a retomada, e depois
  é gravado/finalizado no destino. Só conta como concluído depois que a gravação,
  o tamanho e o registro local de conclusão são confirmados. O temporário é
  removido após sucesso; falhas preservam o temporário para tentar novamente.
- É necessário espaço temporário no aparelho para os arquivos em andamento
  (até o número de downloads simultâneos), além do espaço no destino. Uma cópia
  local pendente de gravação é reutilizada na próxima tentativa, mesmo após
  reiniciar o app, sem baixar novamente o conteúdo já recebido.
- Arquivos existentes não são substituídos: se houver conflito de nome, o novo
  arquivo recebe um sufixo. Trocar o destino não move/apaga arquivos anteriores
  nem repete a busca da galeria. A aba Arquivos mostra o último destino usado.
- Depois de concluir cada imagem, vídeo ou áudio no armazenamento compartilhado,
  o app solicita a indexação ao Android para o conteúdo aparecer nos aplicativos
  de Fotos/Galeria compatíveis.
- Se a permissão for revogada ou a pasta ficar inacessível, o download mostra
  falha e não muda silenciosamente para outra pasta. Escolha a pasta novamente.
- O Android pode impedir selecionar a raiz do armazenamento ou Downloads.
  Crie uma subpasta, por exemplo `Documents/BUIDL` ou `Download/BUIDL`.
  Veja as [restrições oficiais do seletor](https://developer.android.com/training/data-storage/shared/documents-files#grant-access-directory).
- O provedor da pasta precisa permitir criar, gravar, consultar tamanho e
  renomear arquivos. Foi validado o armazenamento local do MuMu; cartões SD e
  provedores de nuvem não foram validados nesta rodada. Em encerramento abrupto
  exatamente durante a finalização, pode restar uma cópia ou `.buidl-*.part`
  incompleta no destino; não é registrada como conclusão sem confirmação.

### Armazenamento e privacidade

- Cookies ficam apenas no armazenamento privado do aplicativo e não são
  incluídos em backups Android, APKs ou exportações.
- **Capturar cookies** abre `https://simpcity.cr/` em um WebView interno. Apenas
  esse domínio e `www.simpcity.cr`, por HTTPS, são permitidos na navegação principal.
  Links externos, arquivos locais e certificados inválidos são bloqueados.
- Faça o login diretamente no site. O BUIDL não extrai os campos de senha,
  não adiciona pontes JavaScript e não registra valores de cookies nos logs.
  Capturas de tela/miniaturas de aplicativos recentes são bloqueadas nessa tela.
- **Pronto** copia os cookies acessíveis na raiz HTTPS (inclusive HttpOnly) e a
  identificação do WebView para um arquivo privado, substituído atomicamente.
  Captura vazia, inválida ou com falha não substitui a sessão anterior. **Voltar**
  não altera os cookies usados pelo downloader; o navegador interno pode manter
  seu próprio login, como qualquer navegador. **Remover sessão salva** limpa ambos.
- Capturar cookies não comprova o login nem impede expiração. O WebView não
  fornece a validade original dos cookies por essa API; o servidor continua
  decidindo quando a sessão deixa de valer. Faça nova captura se necessário.
  A captura usa a API nativa
  [CookieManager.getCookie](https://developer.android.com/reference/android/webkit/CookieManager#getCookie(java.lang.String)).
- Não existe mais fallback de download em `Android/data`: escolher uma pasta pelo
  seletor do Android é obrigatório antes de iniciar qualquer transferência.
- Arquivos concluídos na pasta escolhida permanecem nela ao
  desinstalar. Porém, limpar dados/desinstalar remove permissões, temporários e
  o índice privado de retomada; após reinstalar, será necessário escolher a
  pasta novamente e arquivos antigos podem ser baixados com um novo sufixo.
- Não há upload para um servidor do BUIDL, telemetria ou conta adicional.
- Links HTTP antigos são aceitos por compatibilidade; prefira HTTPS.
- A seleção e a análise ficam na memória enquanto o processo existir. Depois de
  o Android encerrar o processo, analise a URL novamente; os arquivos concluídos
  permanecem na pasta escolhida.

### Limitações

- Requer Android 7+ e processador **arm64-v8a** ou **x86_64**; não inclui ARM 32-bit.
- O APK entregue é uma **compilação de teste/debug**, para instalação manual,
  não uma publicação assinada para a Play Store.
- A prévia utiliza os codecs do Android e depende do host. Quando indisponível,
  mantém a capa ou o cartão do arquivo. Falha de prévia não conta como falha de
  download. A reprodução usa dados da conexão e não tem o limite de bytes do
  player experimental do Windows.
- **Pausar fila/Parar fila** interrompe o início dos próximos arquivos. Operações
  de rede já em andamento podem precisar terminar ou atingir o timeout.
- Downloads longos dependem das regras de bateria/processos do Android. No
  Android 15+, serviços `dataSync` têm limites de duração em segundo plano:
  veja a [documentação oficial](https://developer.android.com/develop/background-work/services/fgs/timeout).
- Não há atualização automática de resolvers nem todas as opções avançadas
  da versão Windows. A seleção de destino obedece às permissões do Android.
- Limite de três downloads simultâneos; a lista de arquivos baixados mostra os
  primeiros 150, mas a exportação inclui todos.
- Sessões expiradas, arquivos removidos e bloqueios dos hosts ainda podem impedir
  um download. Não é possível garantir funcionamento em todos os hosts.
- O site pode restringir navegadores embutidos ou exigir verificações adicionais.
  Cookies e User-Agent iguais não garantem que o servidor aceitará o cliente
  Python. Se a captura não funcionar, use a importação manual. Redirecionamento
  para um novo domínio exigirá atualizar a lista de origens permitidas.

## Compilar no Windows

Ferramentas utilizadas: JDK 21, Gradle 8.13, Android Gradle Plugin 8.13.2,
Android SDK 36/build-tools 36.0.0, Python 3.14 e Chaquopy 17.0.0.

Na raiz do repositório:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File android\build.ps1
```

O script baixa e verifica o SHA-256 do Gradle, usa o SDK instalado e mantém os
caches Gradle dentro de `android`. Se os caminhos forem diferentes, defina
`JAVA_HOME` (JDK 21) e `ANDROID_HOME` antes de executá-lo. `buildPython` usa a
`.venv` Python 3.14 do repositório. O APK fica em
`app/build/outputs/apk/debug/app-debug.apk`.

Para abrir no Android Studio, abra a pasta **android** e escolha **JDK 21** nas
configurações de Gradle. O Java 25 embutido em algumas versões do Studio não é o
runtime usado por esta configuração Gradle 8.13.

`stagePythonEngine` copia somente código de `../src` para a pasta de build,
excluindo os módulos de GUI/prévia Windows. Cookies, downloads, logs pessoais e
executáveis não entram no APK. Não mantenha uma cópia separada dos resolvers.

## Testes

```powershell
.venv\Scripts\python.exe -m pytest -q tests\test_mobile_bridge.py
.venv\Scripts\python.exe android\qa_server.py
```

O servidor de teste usa apenas `127.0.0.1:8876`, cria uma thread e mídias
artificiais e não utiliza cookies pessoais.

Para os testes no MuMu, use a variante **QA isolada** (pacote separado, sem
acessar os cookies ou downloads da instalação normal). O teste de captura usa
uma página offline e cookies fictícios; não envia esses cookies ao site real:

```powershell
adb -s emulator-5554 reverse tcp:8876 tcp:8876
powershell -NoProfile -ExecutionPolicy Bypass -File android\build.ps1 -Task :app:assembleQa -Qa
powershell -NoProfile -ExecutionPolicy Bypass -File android\build.ps1 -Task :app:assembleQaAndroidTest -Qa
adb -s emulator-5554 install -r android\app\build\outputs\apk\qa\app-qa.apk
adb -s emulator-5554 install -r android\app\build\outputs\apk\androidTest\qa\app-qa-androidTest.apk
adb -s emulator-5554 shell am instrument -w -r -e class 'com.sujirobase.buidl.CookieCaptureTest,com.sujirobase.buidl.SmokeTest#fullWorkflow' com.sujirobase.buidl.qa.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5554 reverse --remove tcp:8876
```

Use o serial retornado por `adb devices` se for diferente. Use a variante QA somente
com dados artificiais: seus testes de captura removem cookies do pacote QA. Ao
terminar, remova os pacotes `com.sujirobase.buidl.qa.test` e `com.sujirobase.buidl.qa`
para apagar as amostras e ter uma instalação QA limpa na próxima execução.

O teste `DestinationTest` exige selecionar previamente, pela UI da variante QA,
a pasta exclusiva `Documents/BUIDL-DEST-QA-7f31a9`. Usa arquivos artificiais,
confirma seleção/retomada, colisão de nome sem sobrescrita, gravação automática,
listagem, persistência e revogação da permissão. Executar separadamente:

```powershell
adb -s emulator-5554 shell am instrument -w -r -e class com.sujirobase.buidl.DestinationTest com.sujirobase.buidl.qa.test/androidx.test.runner.AndroidJUnitRunner
```

Ele revoga apenas a permissão QA ao final. As amostras da pasta externa precisam
ser removidas separadamente após conferir os arquivos; não use essa pasta para
dados pessoais. A pasta do aplicativo normal não participa desses testes.

`UiTest` verifica temas, contraste, associação de rótulos, alvos de toque,
texto sem corte vertical/reticências e preservação do formulário/aba ao recriar.
Use `-e populated true` com o servidor local para incluir a galeria preenchida,
e `-e layout portrait` (ou outro nome) para identificar as capturas. Teste com a
fonte do emulador em 1.0/2.0 e retrato/paisagem; anote e restaure os ajustes
originais depois. `android/adb_ui.py qa-screenshots` recolhe apenas PNGs de QA.
