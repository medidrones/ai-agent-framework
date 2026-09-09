# Enforcement de guardrails

O `AgentRuntime` permanece o único proprietário do loop. Guardrails avaliam
valores imutáveis; o `GuardrailManager` resolve os IDs no registry local e cria
um pipeline novo para cada avaliação.

```text
AgentInput
  → INPUT
  → Memory / Knowledge
  → modelo
  → MODEL_OUTPUT
  → TOOL_CALL → aprovação → execução → TOOL_RESULT → próximo turno
  → FINAL_OUTPUT
  → citações
  → memória
  → AgentResult
```

## Ordem normativa de ferramentas

```text
resolve e allowlist
→ permissão
→ validação de schema
→ guardrail de chamada
→ revalidação dos argumentos efetivos
→ aprovação
→ limite e contador
→ execução
→ guardrail de resultado
→ registro e mensagem TOOL
```

Uma rejeição `OPERATION` produz um resultado seguro e permite ao modelo
continuar. Uma rejeição `EXECUTION` conduz ao estado `REJECTED`. Exceções e
resultados incompatíveis conduzem a `FAILED` sem liberar o dado não avaliado.

Checkpoints preservam o input efetivo, resultados efetivos e registros de
guardrail. Uma chamada já avaliada antes da suspensão HITL não é reavaliada na
retomada; replays de `tool_call_id` reutilizam o resultado efetivo registrado.

## Streaming

O enforcement de `MODEL_OUTPUT` e `FINAL_OUTPUT` ocorre após reconstruir a
resposta completa. Deltas já enviados ao consumidor não podem ser retirados se
uma política rejeitar a resposta acumulada. Esta versão não oferece moderação
por delta nem garantia de bloqueio antes da divulgação. Ambientes que exijam
essa garantia devem usar execução não incremental ou buffering em adapter.
