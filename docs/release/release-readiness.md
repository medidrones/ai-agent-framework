# Prontidão da candidata 1.1.0rc2

## Decisão

**READY_FOR_STABLE.** A `1.1.0rc2` foi certificada integralmente com
PostgreSQL 16 e Redis 7.4 reais. Os cinco Owner sign-offs foram confirmados por
Jorge Medina e registrados em
[`evidence/1.1.0rc2/`](evidence/1.1.0rc2/README.md).

O conteúdo funcional continua derivado do commit
`ae2a9741a7184824ae39a83bcea5481e7d6c0ea9`, certificado pelo encerramento do
M01. A `v1.1.0rc1`, no commit
`7af8ebfb8badaf92640154c8fbb9377a0f8c6b11`, permanece imutável e não
certificada porque o job final mediu 89,61% de cobertura ao ignorar 128 testes
de integração sem os serviços reais.

## Gates

| Gate | Estado | Evidência requerida |
| --- | --- | --- |
| Baseline do M01 | PASS | DS-016, 32/32 gates e cinco sign-offs |
| Regressão da fonte RC | PASS | 1.456 testes, zero skips/falhas e cobertura certificada de 94,49% com PostgreSQL 16 e Redis 7.4 reais |
| Qualidade remota | PASS | matriz Ubuntu/Windows em Python 3.12/3.13 |
| Artefatos locais | PASS | 14 artefatos reproduzíveis e instalação limpa em três ambientes |
| Bundle da tag | PASS | 15 checksums, SBOM CycloneDX e evidências vinculadas à tag |
| Certificação da tag | PASS | [workflow 38974750546](https://github.com/medidrones/ai-agent-framework/actions/runs/38974750546) |
| Owner sign-offs da RC | PASS | cinco decisões de Jorge Medina vinculadas aos artefatos da RC |
| P0/P1 abertas | PASS | zero no encerramento certificado do M01 |

O bundle `atlas-v1.1.0rc2` preserva inventário, checksums, SBOM, identidade da
fonte, resultados automatizados e relatórios de instalação dos artefatos. O
digest e as evidências verificadas estão no registro auditável da candidata.

## Próxima decisão

A próxima etapa é o Stable Promotion Gate `1.1.0rc2 → 1.1.0`. A promoção deve
preservar o conteúdo funcional certificado e limitar o delta a versionamento e
metadata de release. Esta decisão não cria a tag estável nem autoriza
publicação no PyPI.
