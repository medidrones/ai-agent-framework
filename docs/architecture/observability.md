# Arquitetura de observabilidade

## Decisão

O runtime depende apenas de contratos do core e recebe um
`ObservabilityManager` por construtor. Adapters concretos dependem desses
contratos e podem traduzir spans e métricas para qualquer backend.

```text
AgentRuntime ──> ObservabilityManager ──> Tracer / MetricsRecorder
                                              ↑
                              adapter opcional de infraestrutura
```

Não há singleton, service locator, `contextvar` obrigatório nem dependência de
OpenTelemetry, Prometheus ou outro fornecedor. Cada execução carrega sua
observação internamente ao runtime, isolando chamadas concorrentes sem colocar
objetos de infraestrutura em `ExecutionState`, snapshots ou checkpoints.

## Fronteiras de responsabilidade

`AgentEvent` é o journal funcional e monotônico da execução. Spans e métricas
são sinais operacionais descartáveis. Uma falha na segunda camada não pode criar,
remover, reordenar ou modificar eventos da primeira.

```text
entrada
  └─ span raiz
      ├─ seleção
      ├─ memória / knowledge / guardrails
      ├─ model turn 1
      ├─ tool real ou aprovação
      ├─ model turn N
      └─ resultado terminal ou suspensão
```

Spans filhos usam o contexto retornado pela raiz. Na suspensão, somente esse
contexto provider-neutral é serializado. A retomada abre outra raiz ligada ao
contexto anterior, sem manter spans abertos durante a espera humana.

## Fail-open e fail-closed

`SafeSpan` e `ObservabilityManager` isolam todas as chamadas de adapters. Isso
inclui erros de criação, atributos, eventos, status, encerramento, métricas e
relógio. O fallback no-op preserva o fluxo do runtime.

Essa decisão é exclusiva da telemetria. Guardrails permanecem fail-closed: uma
avaliação inválida encerra a execução de forma segura e o span apenas observa
esse resultado.

## Streaming

Um único span representa cada model turn incremental. O runtime agrega número
de eventos e tempo até o primeiro delta, evitando cardinalidade e volume por
chunk. Blocos `finally` encerram model span e raiz em sucesso, erro, timeout,
cancelamento e `aclose()` do consumidor. O encerramento é idempotente para
suportar sobreposição segura entre camadas de limpeza.

## Segurança de dados

As allowlists de atributos são separadas para spans e métricas. Spans podem
conter IDs técnicos de correlação necessários ao diagnóstico; métricas não
aceitam esses IDs. Nenhuma fronteira aceita coleções ou objetos arbitrários.
Conteúdo e metadata não são inferidos nem serializados, e exceptions não são
capturadas implicitamente.
