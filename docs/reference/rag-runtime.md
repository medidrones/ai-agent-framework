# Knowledge/RAG no runtime

Nesta versão, RAG significa recuperar evidência externa, acrescentá-la ao
contexto e então gerar a resposta. Não implica busca vetorial.

```text
AgentInput
  → KnowledgeQueryBuilder
  → KnowledgeQuery
  → KnowledgeRetriever
  → validação de protocolo
  → RetrievalPolicy
  → KnowledgeContext + Citation[]
  → KnowledgeContextRenderer
  → ModelMessage(DEVELOPER)
```

## Lifecycle

Quando ao menos uma fonte foi explicitamente habilitada:

```text
VALIDATING_INPUT
  → LOADING_CONTEXT
  → RETRIEVING_KNOWLEDGE
  → RUNNING
```

Memória é carregada em `LOADING_CONTEXT`. Conhecimento externo é recuperado na
fase seguinte. Sem knowledge habilitado, `RETRIEVING_KNOWLEDGE` não ocorre.
Uma busca vazia é válida e continua sem mensagem adicional.

## Ordem do prompt

```text
SYSTEM      instruções do agente
DEVELOPER   memória contextual, quando disponível
DEVELOPER   conhecimento de referência, quando disponível
USER        entrada atual
```

Memória e conhecimento permanecem em mensagens diferentes. O contexto de
knowledge é montado uma única vez, guardado no `ExecutionState` e reutilizado
em todos os turns completos ou incrementais.

## Suspensão e retomada

`ExecutionSnapshot` e `ExecutionCheckpoint` preservam formalmente o
`KnowledgeContext`, incluindo o mapeamento de citações. Na retomada HITL, a
mensagem já presente e o mapeamento são restaurados; o retriever não é chamado
novamente. Isso evita que uma fonte alterada durante a suspensão mude as
evidências da mesma execução.

## Falhas e observabilidade

| Situação | Resultado |
| --- | --- |
| manager ausente | `knowledge_manager_required` |
| fonte inexistente | `knowledge_source_not_found` |
| falha do adapter | `knowledge_retrieval_failed` |
| resultado inválido | `knowledge_protocol_violation` |
| query/contexto inválido | `knowledge_context_error` |
| deadline expirado | `TIMED_OUT` |
| cancelamento externo | `CancelledError` repropagado |

Eventos informam somente comprimento da query, quantidade de fontes e
quantidade selecionada. Texto da consulta, conteúdo documental, URI, metadata e
credenciais não são emitidos.
