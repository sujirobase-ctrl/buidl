# Organização local do BUIDL

O código e os arquivos de configuração permanecem nesta pasta. `build/` e
`dist/` são usados pela compilação atual. `.venv/` e as pastas de cache
mantêm os nomes convencionais das ferramentas.

As 55 pastas/arquivos de builds, distribuições, releases e rascunhos históricos
foram movidos para [Arquivo-BUIDL](Arquivo-BUIDL), separados por tipo.
As versões originais nos nomes foram preservadas para evitar ambiguidades.
Consulte o [mapa completo](Arquivo-BUIDL/Mapa-de-organizacao.json)
para localizar cada item pelo caminho antigo.

A [entrega corrigida sobre a v1.3.0](Correcoes/BUIDL-1.3.0-Correcao-Hosts)
é independente das alterações posteriores presentes neste repositório.

Todas as entregas de correções devem ficar em `Correcoes/`, dentro de uma
subpasta com versão e descrição. Siga as [regras de organização das correções](Correcoes/README.md)
para colocar cada arquivo na pasta certa. Não deixe entregas de correções soltas
na raiz do projeto.

Nenhum arquivo foi apagado e a raiz Git não foi movida.
