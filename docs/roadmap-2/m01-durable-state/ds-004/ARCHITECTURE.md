# Arquitetura da DS-004

## Objetivo

A DS-004 garante consumo único e autorizado do checkpoint PostgreSQL sob
concorrência entre tasks, conexões, processos e réplicas da aplicação.

```text
AgentRuntime.resume(decisão)
        │
        ▼
capability consume_authorized
        │
        ▼
DELETE ... RETURNING ── bloqueio transacional PostgreSQL
        │
        ▼
validar payload, modalidade, request e identidade
        │
        ├── rejeitar/cancelar ──► ROLLBACK ──► checkpoint preservado
        │
        └── autorizar ──────────► COMMIT ────► checkpoint consumido
                                          │
                                          ▼
                               reconstruir ExecutionState
                                          │
                                          ▼
                                  executar ferramenta
```

## Fronteiras

- o core define e coordena autorização, sem depender do PostgreSQL;
- o adapter controla transação, digest do token e SQL atômico;
- o validator injetado controla políticas organizacionais e identidade;
- a ferramenta somente é alcançada depois do retorno confirmado do consumo;
- efeitos externos exatamente uma vez não fazem parte desta garantia.

## Compatibilidade

A capability é privada ao runtime e estrutural. `CheckpointStore` permanece
inalterado; implementações 1.x continuam aceitas pelo fallback histórico.
