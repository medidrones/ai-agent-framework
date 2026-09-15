# Processo de release

1. Respeitar o feature freeze e classificar findings como P0, P1 ou P2.
2. Alterar somente `VERSION` e executar `make sync-version`.
3. Atualizar changelog, compatibilidade e prontidão.
4. Executar `uv sync --locked`, `make quality`, `make reproducible` e
   `make packaging-smoke`.
5. Executar `make release-bundle` para auditorias, benchmark, SBOM e checksums.
6. Compilar clientes .NET e executar exemplos offline e corporativo.
7. Criar tag `vX.Y.ZrcN` somente após revisão humana.
8. Executar o workflow sobre a tag e obter o bundle descrito no
   [gate de aceitação](rc-acceptance-checklist.md).
9. Registrar os cinco sign-offs sem modificar o commit ou os artefatos.

O workflow `Candidata de release` é manual ou acionado por tag RC. Ele valida e
arquiva artefatos, sem permissão ou etapa de publicação no PyPI.

## Validação e promoção

A certificação instala exatamente os wheels gerados, sem modo editável, em
ambientes temporários. Deve conferir metadata, `py.typed`, licenças, namespace,
extras, entry points, SBOM e `SHA256SUMS`.

Uma RC pode manter P2 documentado. A `1.0.0` exige período de validação nas
plataformas suportadas, auditoria de dependências atualizada e nenhum P0/P1.
Publicação é ação separada e explicitamente autorizada.

## Publicação oficial no PyPI por OIDC

O workflow [`Publicação oficial no PyPI`](../../.github/workflows/publish-pypi.yml)
é exclusivamente manual. Seu primeiro job não recebe permissão OIDC: confirma
a tag anotada da versão estável, o commit certificado, o run de empacotamento,
o ID do artefato e todos os checksums do bundle. Os sete jobs de publicação,
um por projeto e environment protegido, recebem `id-token: write` somente
após aprovação. Eles não fazem checkout nem rebuild; cada job publica apenas
seu wheel e sdist do bundle verificado e compara seus SHA-256 com os arquivos
registrados no PyPI. A matriz usa uma execução por vez e interrompe os jobs
restantes se algum falhar, limitando o alcance de um upload parcial.

Para um projeto ainda inexistente no PyPI, a pessoa proprietária deve criar
um Pending Publisher para **cada** uma das sete distribuições, usando o nome
exato do projeto, owner GitHub `medidrones`, repositório
`ai-agent-framework` e workflow `publish-pypi.yml`. Projetos pendentes não
podem compartilhar a mesma identidade OIDC antes do primeiro upload: o core
usa `pypi` e os demais environments têm nomes próprios. Todos exigem
aprovação da conta `medidrones` e são restritos à branch `main`.
Consulte os nomes e o estado em
[`PUBLICATION-STATUS-1.0.1.md`](PUBLICATION-STATUS-1.0.1.md). A criação dos
Pending Publishers não publica nada; o primeiro upload é uma decisão manual
posterior. A GitHub Release em rascunho só pode ser tornada pública depois da
verificação positiva dos sete projetos e dos 14 arquivos no PyPI.

Na configuração inicial dos sete projetos da versão `1.0.1`, o PyPI limitou a
conta a três publicadores pendentes simultâneos. Um primeiro upload converte
o registro pendente em publicador ativo, mas publicar em lotes cria um período
de disponibilidade parcial no registry. Esse desvio do plano original exige
decisão explícita de governança e adaptação do workflow manual para selecionar
somente o lote autorizado. Não executar a matriz completa com registros
pendentes ausentes. Consulte o estado em
[`PUBLICATION-STATUS-1.0.1.md`](PUBLICATION-STATUS-1.0.1.md).

`READY_FOR_RC` autoriza construir o candidato, mas não equivale a
`READY_FOR_STABLE`. Qualquer correção material depois da certificação exige uma
nova versão RC, novo build e nova certificação; evidências de um RC anterior não
podem ser reutilizadas para promover artefatos diferentes.
