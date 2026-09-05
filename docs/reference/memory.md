# Memória

A camada de memória do Atlas representa experiência e contexto associados a
execuções, conversas, agentes ou usuários. Ela é provider-neutral,
storage-agnostic e somente é ativada quando o agente declara uma configuração
explícita.

Memória não é Knowledge/RAG. Registros de memória normalmente derivam da
experiência do agente; documentos, corpora externos, embeddings e recuperação
de conhecimento pertencem a outra camada.

## Contratos

`MemoryType` possui três valores estáveis:

| Tipo | Intenção | Escopo padrão seguro |
| --- | --- | --- |
| `WORKING` | fatos transitórios da execução | execução + agente |
| `CONVERSATION` | contexto conversacional | sessão + agente |
| `LONG_TERM` | preferência ou fato durável | usuário/identidade + agente |

Quando disponível, `tenant_id` também integra o escopo. Um `MemoryScope` vazio,
com identificador em branco ou wildcard global é inválido. A policy padrão não
inventa IDs: conversa sem `session_id` e longo prazo sem usuário ou identidade
estável produzem `memory_scope_unavailable`.

Os value objects são imutáveis e serializáveis:

- `MemoryRecord`: ID definitivo, tipo, escopo, conteúdo textual, timestamps,
  expiração opcional e metadados;
- `MemoryWriteRequest`: escrita append-oriented sem exigir ID do consumidor;
- `MemoryQuery`: um tipo, um escopo exato, texto opcional e limite positivo;
- `MemorySearchResult`: registro e score opcional específico do store;
- `MemoryCandidate`: conteúdo escolhido por uma policy antes da resolução do
  escopo.

Scores não são comparáveis entre stores. `MemoryQuery.text` também não promete
busca semântica: cada adapter pode implementar busca lexical ou outra semântica
documentada.

## Store e manager

O core define apenas o protocolo assíncrono `MemoryStore`:

```python
class MemoryStore(Protocol):
    async def get(
        self, memory_id: str, *, scope: MemoryScope
    ) -> MemoryRecord | None: ...
    async def write(self, request: MemoryWriteRequest) -> MemoryRecord: ...
    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]: ...
    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool: ...
```

`get()` e `delete()` sempre exigem escopo, reduzindo o risco de acesso cruzado
por ID. O core não fornece banco, cache ou store concreto.

`MemoryManager` não guarda estado de execução. Ele normaliza falhas inesperadas
do adapter, filtra registros expirados e rejeita resultados com escopo, tipo ou
IDs incompatíveis. A seleção padrão preserva a ordem do store, respeita o
limite e pula registros que não cabem inteiros no orçamento de caracteres; não
trunca, resume nem reranqueia.

## Configuração do agente

```python
agent = AgentDefinition(
    agent_id="assistant",
    name="Assistente",
    instructions="Ajude o usuário.",
    memory=AgentMemoryConfig(
        read_types=frozenset({MemoryType.CONVERSATION, MemoryType.LONG_TERM}),
        write_types=frozenset({MemoryType.CONVERSATION}),
        max_records_per_type=20,
        max_characters=8_000,
    ),
)
```

Sem `memory`, ou com configuração vazia, o comportamento anterior é mantido.
Injetar um `MemoryManager` não ativa memória silenciosamente. Se um agente
habilitar leitura ou escrita sem manager, a execução falha com
`memory_manager_required`.

## Recuperação e fronteira do prompt

O runtime consulta os tipos habilitados sempre na ordem `WORKING`,
`CONVERSATION`, `LONG_TERM`, uma vez por execução:

```text
AgentInput
  → MemoryScopePolicy
  → MemoryQuery
  → MemoryStore.search()
  → MemoryManager
  → MemorySelectionPolicy
  → MemoryContextRenderer
  → ModelMessage(DEVELOPER)
```

A mensagem fica entre as mensagens `SYSTEM` e `USER`. Um framing fixo afirma
que os registros são dados contextuais não confiáveis e não podem substituir
instruções. Conteúdo, IDs, metadados e scores não entram nos eventos. A mensagem
é acrescentada uma única vez ao `ExecutionState`, sendo reutilizada nos turnos
seguintes e preservada pelo checkpoint durante suspensões HITL.

## Escrita

O runtime não decide sozinho o que merece ser lembrado. A implementação padrão
`NoMemoryWritePolicy` não cria candidatas. Uma `MemoryWritePolicy` explicitamente
injetada recebe o `ExecutionSnapshot` e o output validado:

```text
output validado
  → MemoryWritePolicy
  → MemoryCandidate[]
  → validação de write_types
  → resolução de escopo
  → UPDATING_MEMORY
  → MemoryStore.write() sequencial
  → COMPLETED
```

Uma candidata de tipo não autorizado produz `memory_policy_violation`. Falha
de escrita produz `memory_write_failed`, sem output terminal, mas preservando o
uso. Sem candidatas, o lifecycle segue diretamente de `VALIDATING_OUTPUT` para
`COMPLETED`. Execuções rejeitadas, suspensas, canceladas ou com falha não
escrevem memória.

Busca e escrita obedecem ao timeout total do runtime e preservam o cancelamento
cooperativo. Não existem retry, fallback, deduplicação, upsert, consolidação,
sumarização por LLM ou persistência concreta nesta versão.
