# Roadmap 2 — Ecosystem & Enterprise

O Roadmap 2 expande as implementações do Atlas sem romper os contratos públicos
da linha 1.x. Cada marco possui escopo, evidências e gate formal próprios; a
conclusão de um marco não autoriza automaticamente o próximo.

## Estado atual

| Marco | Objetivo | Estado |
| --- | --- | --- |
| M01 | Durable State | `COMPLETE` · `CERTIFIED` · publicado em `1.1.0` |
| M02 | Enterprise Memory | próximo marco planejado · não iniciado |
| M03 | Enterprise Knowledge / RAG | planejado |
| M04 | Provider Expansion | planejado |
| M05 | Enterprise Observability | planejado |
| M06 | Messaging & Integration | planejado |
| M07 | Cross-Stack SDKs | planejado |
| M08 | Conformance & Certification | planejado |
| M09 | Production Hardening | planejado |
| M10 | Atlas 1.x LTS | planejado |

## Baseline publicada

- versão: `1.1.0`;
- M01: DS-001–DS-016 concluídas;
- certificação técnica e cinco owner sign-offs: `PASS`;
- sete distribuições publicadas no PyPI por Trusted Publishing;
- contratos públicos do Atlas 1.x preservados;
- pendências P0/P1 no fechamento do M01: `0/0`.

A evidência congelada da DS-016 registra o estado no instante da certificação e
deve permanecer inalterada. A promoção, a release e a publicação posteriores
estão registradas na [documentação da versão 1.1.0](../release/releases/1.1.0.md).

## Navegação

- [Fechamento do M01 — Durable State](m01-durable-state/README.md)
- [Arquitetura implementada](../architecture/implemented-architecture.md)
- [Diagrama atualizado do Roadmap 2](../architecture/atlas-roadmap-2-architecture.svg)
- [Status da promoção estável](../release/STABLE-PROMOTION-STATUS.md)

## Próximo marco

O próximo marco planejado é o **M02 — Enterprise Memory**. Ele permanece
`NOT_STARTED` até que seu escopo e sua autorização formal sejam registrados.
Não há implementação do M02 implícita no encerramento do M01.
