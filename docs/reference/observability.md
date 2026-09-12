# Observabilidade

O core oferece contratos neutros de provedor para tracing e métricas, integrados
ao `AgentRuntime` por injeção explícita. Sem configuração, implementações no-op
mantêm o mesmo comportamento funcional e não exigem dependências adicionais.

## Configuração

```python
from atlas_agents import AgentRuntime, ObservabilityManager

observability = ObservabilityManager(
    tracer=meu_tracer,
    metrics=meu_registrador_de_metricas,
)
runtime = AgentRuntime(
    model_registry=registry,
    observability_manager=observability,
)
```

Adapters implementam `Tracer`, `Span` e `MetricsRecorder`. Esses contratos são
síncronos e devem apenas registrar dados localmente ou enfileirá-los; exportação
com I/O pertence ao adapter. `NoOpTracer`, `NoOpSpan` e
`NoOpMetricsRecorder` são os padrões seguros.

`TraceContext` transporta `trace_id`, `span_id`, `trace_flags` e `trace_state`
como strings opacas. O consumidor pode fornecê-lo em `AgentContext`. Quando uma
execução é suspensa, o checkpoint preserva somente esse contexto operacional;
o token de retomada nunca é incluído. A retomada cria uma nova raiz cujo parent
é o contexto salvo.

## Spans do runtime

| Span | Quando ocorre | Dados seguros principais |
| --- | --- | --- |
| `atlas.agent.execution` | `run`, `stream`, `resume` e `resume_stream` | modo, retomada, status e outcome |
| `atlas.model.select` | seleção e resolução do provider/model | provider e model selecionados |
| `atlas.model.generate` | cada model turn completo | turn, finish reason, usage e custo |
| `atlas.model.stream` | cada model turn incremental | contagem agregada de eventos |
| `atlas.tool.execute` | somente execução real da ferramenta | nome e status |
| `atlas.approval.evaluate` | avaliação de aprovação | decisão, sem justificativa |
| `atlas.checkpoint.save` | persistência da suspensão | operação e status |
| `atlas.checkpoint.consume` | consumo para retomada | operação e status |
| `atlas.memory.retrieve` | leitura por tipo de memória | tipo e quantidade |
| `atlas.memory.write` | escrita efetiva | tipo e status |
| `atlas.knowledge.retrieve` | recuperação RAG | quantidades de fontes e resultados |
| `atlas.guardrail.evaluate` | pipeline por estágio | estágio, decisão e quantidade |

Não há span por delta de streaming. O span do model turn agrega a quantidade de
eventos e a métrica de tempo até o primeiro delta. Fechamento normal, timeout,
cancelamento e encerramento antecipado do consumidor encerram os spans uma única
vez.

## Status e outcomes

O status técnico do span não redefine o lifecycle:

| Resultado do runtime | Status da raiz |
| --- | --- |
| `completed`, `rejected`, `suspended`, `limit_exceeded`, `budget_exceeded` | `OK` |
| `failed`, `timed_out` | `ERROR` |
| cancelamento externo ou fechamento antecipado | `UNSET` |

Rejeição por política é um resultado esperado, não falha de telemetria. Falha de
uma ferramenta marca seu próprio span como `ERROR`, mesmo quando o loop converte
o resultado e continua com segurança.

## Métricas e cardinalidade

O runtime registra contadores e durações para execuções, modelos, ferramentas,
aprovação, checkpoints, memória, conhecimento e guardrails. Labels aceitas são
limitadas a dimensões estáveis como `mode`, `resumed`, `outcome`, `status`,
`provider`, `model`, `tool_name`, `stage`, `decision`, `operation` e
`memory_type`.

IDs de execução, request, chamada, trace, usuário, sessão ou conversa nunca são
labels de métrica. `SafeAttributeBuilder`, `safe_span_attributes()` e
`safe_metric_attributes()` aplicam allowlists e aceitam somente escalares.

## Privacidade e tratamento de falhas

A instrumentação não registra input/output, prompts, argumentos ou resultados
de ferramentas, conteúdo de memória ou conhecimento, justificativas de
aprovação, tokens de retomada, credenciais ou metadata arbitrária. Exceptions e
stack traces não são capturadas automaticamente. Um adapter pode expor captura
explícita por `Span.record_exception()`, cabendo ao integrador aplicar redação.

Todas as operações de observabilidade são fail-open: falhas ao iniciar ou
atualizar spans, registrar métricas ou consultar o relógio são absorvidas e não
alteram resultados, eventos, sequência, checkpoints ou cancelamento. Guardrails
continuam fail-closed; essa regra não é relaxada pela observabilidade.

## Matriz normativa

| # | Garantia | Evidência automatizada |
| ---: | --- | --- |
| 1 | contratos públicos provider-neutral | `test_observability_contracts_are_intentionally_public` |
| 2 | contexto serializável e imutável | `test_contracts.py` |
| 3 | IDs opacos | `test_contracts.py` |
| 4 | valores em branco rejeitados | `test_contracts.py` |
| 5 | enums estáveis | `test_contracts.py` |
| 6 | defaults no-op | `test_contracts.py` |
| 7 | ausência de SDK concreto | `test_observability_contracts_have_no_runtime_or_vendor_coupling` |
| 8 | injeção por instância | `test_manager.py` |
| 9 | falha ao iniciar span é absorvida | `test_manager.py` |
| 10 | falha ao operar span é absorvida | `test_manager.py` |
| 11 | falha de métricas é absorvida | `test_manager.py` |
| 12 | encerramento idempotente | `test_manager.py` |
| 13 | atributos escalares e allowlist | `test_manager.py` |
| 14 | labels de baixa cardinalidade | `test_manager.py` |
| 15 | raiz usa parent recebido | `test_successful_run_records_root_selection_model_and_safe_metrics` |
| 16 | seleção e geração instrumentadas | mesmo teste de execução bem-sucedida |
| 17 | usage e custo agregados | mesmo teste de execução bem-sucedida |
| 18 | telemetria não altera journal | `test_broken_telemetry_preserves_result_and_event_journal` |
| 19 | mapeamento de rejeição e falha | `test_root_outcome_mapping_for_rejection_and_failure` |
| 20 | mapeamento de limite e budget | `test_limit_budget_timeout_and_cancellation_span_mapping` |
| 21 | timeout e cancelamento distintos | mesmo teste de limites |
| 22 | streaming agrega eventos | `test_stream_spans_complete_and_close_early_without_leaks` |
| 23 | fechamento antecipado não vaza span | mesmo teste de streaming |
| 24 | replay não duplica tool span | `test_multi_turn_tool_execution_and_duplicate_replay_are_counted_once` |
| 25 | caminho inválido não cria tool span | `test_denied_or_invalid_tool_does_not_create_execution_span` |
| 26 | falha real de ferramenta é `ERROR` | `test_tool_failure_marks_only_actual_execution_span_as_error` |
| 27 | checkpoint preserva parent, não token | `test_hitl_checkpoint_preserves_trace_and_resume_parent` |
| 28 | retomada streaming preserva trace | `test_resume_stream_continues_trace_and_instruments_stream_mode` |
| 29 | memória e knowledge não vazam conteúdo | `test_memory_and_knowledge_instrumentation_is_content_free` |
| 30 | guardrail mantém fail-closed sem exception crua | `test_guardrail_exception_is_fail_closed_without_raw_exception_telemetry` |

## Limitações atuais

O core não inclui exporter, collector, backend, sampling distribuído nem
propagadores HTTP. A continuidade é feita por `TraceContext` explícito. A versão
atual do checkpoint permanece compatível porque o novo campo é opcional. O span
de consumo pode existir antes da raiz da retomada: somente após ler e validar o
checkpoint é possível conhecer o parent salvo.
