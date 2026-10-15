# Auditoria de arquitetura do M01

## Escopo e baseline

- candidato técnico: `89f00dfd3754871ca4640f3fd258aeb7e7259bc7`;
- baseline pública preservada: Atlas `1.0.1`, tag no commit
  `aa766c72c9bfb61d998c2e98b36dc4d44a1953ec`;
- data da revalidação: 15/10/2026;
- decisões aplicáveis: ADR-001 a ADR-010.

## Resultado

| Invariante | Evidência | Resultado |
| --- | --- | --- |
| inversão de dependência | `atlas-agent-core` não possui dependência de banco, broker, framework web ou SDK de modelo | PASS |
| infraestrutura opcional | PostgreSQL e Redis permanecem extras de `atlas-agent-adapters` | PASS |
| grafo acíclico | testes de arquitetura e auditoria do grafo | PASS |
| ownership do runtime | ADR-001 e testes de runtime | PASS |
| contratos provider-neutral | contratos de checkpoint, lease, recovery, retenção e purge no core | PASS |
| I/O assíncrono e DI | adapters recebem pools/clientes por construtor | PASS |
| compatibilidade 1.x | capabilities novas são aditivas; contratos mínimos permanecem | PASS |

O grafo observado é `adapters -> core`, `providers -> core`, `mcp -> core`,
`evaluation -> core` e `config -> core/adapters`. Não foram detectados ciclos.
`uv run pytest` incluiu os testes de arquitetura e terminou com 1.455 aprovações.

## Limites preservados

Não há promessa de exactly-once para efeitos externos. Redis Cluster e Sentinel
não fazem parte da certificação. Autenticação de pessoas e autorização de host
continuam fora do core, conforme ADR-010.

**Decisão:** `ARCHITECTURE = VERIFIED`.
