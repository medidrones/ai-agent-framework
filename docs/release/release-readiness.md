# Prontidão da candidata 1.1.0rc1

## Decisão

**NOT_CERTIFIED.** A fonte do M01 está autorizada a preparar a candidata
`1.1.0rc1`, mas a tag e os artefatos próprios dessa versão ainda não foram
gerados nem certificados. As evidências da DS-016 autorizam iniciar o ciclo;
elas não substituem os gates da candidata.

O conteúdo funcional de origem está no commit
`ae2a9741a7184824ae39a83bcea5481e7d6c0ea9`, certificado pelo encerramento do
M01. A preparação permite somente versionamento lockstep, restrições internas,
changelog e metadata de release.

## Gates

| Gate | Estado | Evidência requerida |
| --- | --- | --- |
| Baseline do M01 | PASS | DS-016, 32/32 gates e cinco sign-offs |
| Regressão da fonte RC | PASS | 1.455 testes, zero skip/falha, cobertura 92,68% com PostgreSQL 16 e Redis 7.4 reais |
| Qualidade remota | PENDENTE | matriz Ubuntu/Windows em Python 3.12/3.13 |
| Artefatos locais | PASS | sete wheels, sete sdists, reprodução e instalação limpa verificadas |
| Bundle da tag | PENDENTE | checksums, SBOM e evidências vinculadas à futura tag |
| Certificação da tag | PENDENTE | workflow sobre a futura `v1.1.0rc1` |
| Owner sign-offs da RC | PENDENTE | decisões vinculadas aos artefatos da RC |
| P0/P1 abertas | PASS | zero no encerramento certificado do M01 |

O bundle esperado deverá preservar inventário, checksums, SBOM, identidade da
fonte, resultados automatizados e relatórios de instalação dos artefatos. Esses
registros ainda não existem para `1.1.0rc1` e não podem ser herdados de uma
versão anterior.

## Próxima decisão

Após os gates locais da fonte passarem, a preparação poderá ser submetida para
revisão. Criar e publicar a tag anotada `v1.1.0rc1` permanece uma ação separada.
Somente o bundle produzido sobre essa tag poderá sustentar a decisão
`READY_FOR_STABLE`.
