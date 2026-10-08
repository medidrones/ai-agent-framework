# Relatório de certificação DS-002

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-002 — PostgreSQLCheckpointStore
- Baseline: Atlas `1.0.1`
- Commit-base integrado: `88e62e2bdce7c6be0c5102a561d0de81b6ded341`
- Branch: `medicode/ds-002-postgresql-checkpoint-store`
- Data da certificação local: 2026-10-08
- DS-001: `CERTIFIED`

## Resultado

O `PostgreSQLCheckpointStore` implementa estruturalmente o contrato público
`CheckpointStore` sem alterar o `AgentRuntime` ou as APIs públicas 1.x. A
dependência Psycopg está isolada no extra `atlas-agent-adapters[postgresql]`.
O gate Python 3.13 revelou e corrigiu a ordenação não determinística de
capabilities na serialização JSON do core, preservando campos, tipos e valores.

Persistência e consumo usam transações gerenciadas pelo pool injetado. O
consumo é um único `DELETE ... RETURNING`, que garante somente um vencedor sob
concorrência e impede replay do token. O lifecycle das conexões pertence à
aplicação; o adapter não lê ambiente nem cria estado global.

Migrations SQL são versionadas, empacotadas, verificadas por checksum e
serializadas por advisory lock transacional. A integração sobre PostgreSQL 16
real validou restart do pool, cancelamento, concorrência e retomada HITL.

## Decisão sobre o gap crítico da DS-001

`DS001-GAP-001` foi formalmente limitado pela
`ADR-002-postgresql-checkpoint-consumption-semantics.md`. A DS-002 garante
**at-most-once para autorização de retomada**, mas não declara exactly-once para
efeitos externos. O risco entre consumo destrutivo e efeito da ferramenta não é
ocultado nem reinterpretado como resolvido; qualquer protocolo claim/ack,
receipt, outbox ou recovery journal exige decisão arquitetural futura.

Essa decisão preserva o contrato 1.x e satisfaz a autorização de governança para
iniciar a DS-002 sem modificar o `AgentRuntime`.

## Gates obrigatórios

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS002-G01 — DS-001 certificada | PASS | relatório DS-001 com decisão `CERTIFIED` |
| DS002-G02 — gap crítico decidido | PASS | ADR-002; escopo at-most-once explícito |
| DS002-G03 — contratos 1.x preservados | PASS | assinaturas, campos, tipos e valores preservados; JSON canônico entre versões Python |
| DS002-G04 — dependência isolada | PASS | extra `postgresql` somente nos adapters |
| DS002-G05 — persistência transacional | PASS | PostgreSQL real e testes de integração |
| DS002-G06 — consumo atômico e replay | PASS | um vencedor em doze consumidores; replay rejeitado |
| DS002-G07 — migrations versionadas | PASS | migration 001, checksum e advisory lock |
| DS002-G08 — conexões explícitas | PASS | pool injetado e pertencente à aplicação |
| DS002-G09 — restart e HITL | PASS | recriação do pool e fluxo `run/resume` real |
| DS002-G10 — cancelamento | PASS | rollback sem perda do checkpoint |
| DS002-G11 — segurança | PASS | digest/HMAC, SQL parametrizado, erros seguros e Bandit |
| DS002-G12 — unitários/negativos | PASS | configuração, colisão, expiração, corrupção e indisponibilidade |
| DS002-G13 — integração real | PASS | 15 testes PostgreSQL aprovados |
| DS002-G14 — regressão completa | PASS | 1.175 testes; cobertura 92,91% |
| DS002-G15 — lint/formato/tipos | PASS | Ruff e mypy aprovados |
| DS002-G16 — distribuição | PASS | builds, Twine, wheel e instalação limpa aprovados |
| DS002-G17 — documentação pública | PASS | guia de uso, instalação, semântica e operação |
| DS002-G18 — relatório final | PASS | este documento e `TEST-EVIDENCE.md` |

## Gaps e limitações preservados

- Não há exactly-once para efeitos externos; a ADR-002 proíbe essa alegação.
- O lookup continua baseado no bearer token conforme o contrato 1.x. O tenant é
  persistido para rastreabilidade, mas não participa da assinatura de
  `consume()`.
- Payloads podem conter dados sensíveis. Criptografia, backup e controle de
  acesso ao banco pertencem à plataforma hospedeira.
- Payload inválido é consumido e rejeitado em modo fail-closed, pois a validação
  posterior ao consumo é a semântica certificada do runtime 1.x.
- Não há CAS, lease, fencing, enumeração administrativa nem upcaster de schema.
  Esses itens não foram acrescentados implicitamente à DS-002.
- Redis está integralmente fora desta entrega.
- Os checks remotos são evidências externas mantidas no pull request e devem
  estar aprovados antes do merge.

Nenhuma limitação acima é uma falha oculta dos gates executados. Elas delimitam
as garantias públicas e o trabalho futuro sem antecipar a DS-003.

## Decisão

Todos os gates obrigatórios executáveis no candidato local passaram. O gap
crítico da DS-001 possui decisão formal e nenhuma alteração incompatível foi
introduzida.

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-002

BASELINE VERSION          1.0.1
TASK                      PostgreSQLCheckpointStore

DS001 CERTIFICATION       CERTIFIED
CRITICAL GAP DECISION     APPROVED_BY_ADR
PUBLIC CONTRACTS          UNCHANGED
CORE POSTGRESQL DEPS      NONE
TRANSACTIONAL SAVE        PASS
ATOMIC CONSUME            PASS
CONCURRENCY               PASS
REPLAY PROTECTION         PASS
MIGRATIONS                PASS
CONNECTION LIFECYCLE      PASS
RESTART RECOVERY          PASS
HITL INTEGRATION          PASS
SECURITY                  PASS

TESTS PASSED              1175
TESTS FAILED              0
POSTGRESQL TESTS          15
COVERAGE                  92.91%
BUILD                     PASS
CLEAN INSTALL             PASS

FINAL DECISION            COMPLETE
NEXT TASK                 DS-003 (NOT STARTED)
```
