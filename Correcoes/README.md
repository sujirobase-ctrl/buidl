# Pasta de correções

Todas as entregas de correções devem ficar nesta pasta, separadas por versão
e descrição. Não deixe executáveis, ZIPs ou relatórios de correções soltos na
raiz do projeto.

Exemplo: `Correcoes/BUIDL-1.3.0-Correcao-Hosts/`.

Dentro de cada entrega, coloque os arquivos na pasta certa:

| Pasta | Conteúdo |
| --- | --- |
| `Windows/` | Executáveis de Windows: GUI, CLI e batch. |
| `Android/` | APKs, quando forem gerados e testados. |
| `Codigo-fonte/` | Pacote do código-fonte correspondente à correção. |
| `Documentacao/` | Relatório das mudanças, versão base, testes e limitações. |
| `Pacotes/` | ZIPs portáteis para distribuição. |

Crie apenas as subpastas necessárias para a entrega. Os hashes de integridade
ficam em `SHA256SUMS.txt` dentro da própria entrega.

As alterações de código devem ser feitas nos arquivos dos módulos corretos
da versão base solicitada, como `src/`, `android/` ou `windows-dotnet/`, e os
testes devem ficar em `tests/`. Esta pasta reúne as entregas; não substitui a
estrutura do código-fonte nem recebe cópias soltas de arquivos Python.

Mantenha os arquivos históricos em `Arquivo-BUIDL/` e os arquivos intermediários
da compilação em `build/` e `dist/`. Não misture versões diferentes na mesma
entrega nem substitua uma entrega existente sem identificar sua revisão.

## Ícone personalizado — 1.4.5

[BUIDL 1.4.5](BUIDL-1.4.5-Icone/).
Executável: `BUIDL-1.4.5-Icone/Windows/BUIDL-1.4.5.exe`.

## Capas automáticas e reprodução ao clicar — 1.4.4

[BUIDL 1.4.4](BUIDL-1.4.4-Capas-Video/).
Executável: `BUIDL-1.4.4-Capas-Video/Windows/BUIDL-1.4.4.exe`.

## Vídeos ampliados e prévia de 10 segundos — 1.4.3

[BUIDL 1.4.3](BUIDL-1.4.3-Previa-Video/).
Executável: `BUIDL-1.4.3-Previa-Video/Windows/BUIDL-1.4.3.exe`.

## Galeria alinhada e ampliação interna — 1.4.2

[BUIDL 1.4.2](BUIDL-1.4.2-Galeria-Alinhada/).
Executável: `BUIDL-1.4.2-Galeria-Alinhada/Windows/BUIDL-1.4.2.exe`.

## Miniaturas corrigidas — 1.4.1

[BUIDL 1.4.1 — Miniaturas](BUIDL-1.4.1-Miniaturas/).
Executável: `BUIDL-1.4.1-Miniaturas/Windows/BUIDL-1.4.1.exe`.

## Nova interface disponível

[BUIDL 1.4.0 — Nova interface](BUIDL-1.4.0-Nova-Interface/).
Executável: `BUIDL-1.4.0-Nova-Interface/Windows/BUIDL-1.4.0.exe`.
Base 1.3.0 corrigida; cópia isolada, com relatório de testes.

## Correção disponível

[BUIDL v1.3.0 — HTTPS e destino corrigidos](BUIDL-1.3.0-HTTPS-Destino/).
**Interface clássica corrigida:** `BUIDL-1.3.0-HTTPS-Destino/Windows/BUIDL-GUI.exe`.

[BUIDL v1.3.0 — downloads longos e retomada](BUIDL-1.3.0-Downloads-Longos/).
Entrega anterior, preservada para histórico.

[BUIDL v1.3.0 — correção dos hosts](BUIDL-1.3.0-Correcao-Hosts/).
Para executar, abra `BUIDL-1.3.0-Correcao-Hosts/Windows/BUIDL-GUI.exe`.

## Android 1.4.5

Entrega baseada na versão Windows 1.4.5, com interface nativa Android e testes no MuMu.

- [APK](BUIDL-1.4.5-Android/Android/BUIDL-1.4.5-Android.apk)
- [Relatório de validação](BUIDL-1.4.5-Android/Documentacao/Relatorio-Android-1.4.5.md)
- [Fontes](BUIDL-1.4.5-Android/Codigo-fonte/README.md)

A versão Windows 1.4.5 permanece em BUIDL-1.4.5-Icone.
