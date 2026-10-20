# Relatório de certificação — OR-001

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M02 — OR-001

BASELINE                  1.1.0
TASK                      Architecture & Orchestration Contracts

COMMIT SHA                f32e67b1a51c453bc6b78885cf0b650ea09137f5

ARCHITECTURE              PASS
WORKFLOW CONTRACTS        PASS
PUBLIC API                PASS
SERIALIZATION             PASS
IMMUTABILITY              PASS
SECURITY                  PASS
DEPENDENCY ISOLATION      PASS
AGENTRUNTIME COMPAT       PASS
DURABLE STATE BOUNDARY    PASS
QUALITY GATES             PASS
DOCUMENTATION             PASS

ACCEPTANCE GATES          30/30 PASS

TESTS PASSED              1398
TESTS FAILED              0
TESTS SKIPPED             128
COVERAGE                  90.00%

CRITICAL GAPS             0
HIGH BLOCKING GAPS        0

FINAL DECISION            COMPLETE
NEXT TASK                 OR-002
```

## Baseline e rastreabilidade

- branch: `medicode/or-001-contracts`;
- commit inicial: `fb060b436d68f70248a240bbec4dfbe33b8715f1`;
- tag publicada `v1.1.0`: `116e886e95c8785920ca1f18e6d88b01a3c1e3ed`;
- commit certificado: `f32e67b1a51c453bc6b78885cf0b650ea09137f5`;
- ambiente: Windows, CPython 3.13.15, uv;
- data do fechamento: 2026-10-20.

A diferença entre a tag e o commit inicial contém o fechamento documental
posterior do M01. A OR-001 não modificou a tag ou o histórico publicado.

## Acceptance gates

| Gate | Evidência | Resultado |
| --- | --- | --- |
| OR001-G01 | tag e versão 1.1.0 verificadas | PASS |
| OR001-G02 | `AGENTS.md`, ADR-001–ADR-010 e arquitetura inspecionados | PASS |
| OR001-G03 | `ARCHITECTURE.md` da tarefa | PASS |
| OR001-G04 | `WorkflowDefinition` | PASS |
| OR001-G05 | `WorkflowNode` | PASS |
| OR001-G06 | `WorkflowEdge` | PASS |
| OR001-G07 | `WorkflowInput` | PASS |
| OR001-G08 | `WorkflowContext` | PASS |
| OR001-G09 | `WorkflowStatus` | PASS |
| OR001-G10 | `WorkflowResult` e resultados de nós | PASS |
| OR001-G11 | `WorkflowEvent` | PASS |
| OR001-G12 | `WorkflowEventType` | PASS |
| OR001-G13 | protocolo assíncrono `WorkflowOrchestrator` | PASS |
| OR001-G14 | sete policy contracts explícitos | PASS |
| OR001-G15 | exceções derivadas de `AtlasAgentError` | PASS |
| OR001-G16 | identidades distintas e correlação | PASS |
| OR001-G17 | validação estrutural básica | PASS |
| OR001-G18 | round-trip e JSON bounded | PASS |
| OR001-G19 | modelos e containers profundamente imutáveis | PASS |
| OR001-G20 | cenários negativos de segurança | PASS |
| OR001-G21 | testes de imports proibidos | PASS |
| OR001-G22 | `AgentRuntime` sem dependência do orquestrador | PASS |
| OR001-G23 | ADR-015 e `DURABLE-STATE-INTEGRATION.md` | PASS |
| OR001-G24 | exports de `atlas_agents` validados | PASS |
| OR001-G25 | versão, runtime e contratos 1.1.0 preservados | PASS |
| OR001-G26 | matriz unitária OR001-T01–T25 | PASS |
| OR001-G27 | OR001-T26–T29 e guardrails arquiteturais | PASS |
| OR001-G28 | uv, Ruff, mypy, pytest e build | PASS |
| OR001-G29 | cinco ADRs e doze documentos obrigatórios | PASS |
| OR001-G30 | este relatório com evidências verificáveis | PASS |

## Quality gates

| Comando/verificação | Evidência |
| --- | --- |
| `uv sync` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS · 843 arquivos |
| `uv run mypy packages` | PASS · 388 arquivos-fonte |
| `uv run pytest` | PASS · 1.398 passed · 128 skipped · 0 failed |
| cobertura com branches | PASS · 90,00% |
| `uv build --package atlas-agent-core` | PASS · wheel e sdist |
| instalação limpa do wheel | PASS · sem editable install |
| imports públicos e `py.typed` | PASS |

Os skips correspondem a integrações dependentes de serviços externos já
presentes na baseline. Nenhum teste existente foi desabilitado.

## Findings e limites preservados

- findings críticos: 0;
- findings altos bloqueantes: 0;
- a primeira tentativa de clean install usou `--no-index` antes das
  dependências e falhou na resolução de `jsonschema`; o procedimento correto
  foi repetido em venv novo, instalando dependências declaradas e depois o wheel
  local com `--no-deps --no-index`, com resultado `PASS`;
- os limites de payload são os valores documentados em `SERIALIZATION.md`;
- não há engine, scheduler, validação completa de DAG, worker, broker,
  paralelismo, retry, compensação ou persistência de workflow;
- `tenant_id` não representa autorização;
- o M01 será reutilizado futuramente por composição, sem novo backend no core.

## Decisão

A regra de certificação foi satisfeita. `OR001 = COMPLETE`. A OR-002 está
liberada como próxima tarefa de governança, mas não foi iniciada nem antecipada
nesta entrega.
