# Processo de release

1. Respeitar o feature freeze e classificar findings como P0, P1 ou P2.
2. Alterar somente `VERSION` e executar `make sync-version`.
3. Atualizar changelog, compatibilidade e prontidão.
4. Executar `uv sync --locked`, `make quality`, `make reproducible` e
   `make packaging-smoke`.
5. Executar `make release-bundle` para auditorias, benchmark, SBOM e checksums.
6. Compilar clientes .NET e executar exemplos offline e corporativo.
7. Criar tag `vX.Y.ZrcN` somente após revisão humana.

O workflow `Candidata de release` é manual ou acionado por tag RC. Ele valida e
arquiva artefatos, sem permissão ou etapa de publicação no PyPI.

## Validação e promoção

A certificação instala exatamente os wheels gerados, sem modo editável, em
ambientes temporários. Deve conferir metadata, `py.typed`, licenças, namespace,
extras, entry points, SBOM e `SHA256SUMS`.

Uma RC pode manter P2 documentado. A `1.0.0` exige período de validação nas
plataformas suportadas, auditoria de dependências atualizada e nenhum P0/P1.
Publicação é ação separada e explicitamente autorizada.
