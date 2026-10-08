# Inventário de contratos de persistência

## Escopo certificado

Baseline: Atlas `1.0.1`, tag imutável no commit
`43fd7008f8573f2b2a9906ee8c257986777f04e9`. A auditoria foi executada na
branch `medicode/ds-001-persistence-contract-certification`, sem alterar APIs do
core e sem adicionar implementação de infraestrutura.

## Contratos públicos

| Contrato | Responsabilidade | Evidência |
| --- | --- | --- |
| `ExecutionCheckpoint` | Estado imutável e serializável necessário à retomada | `runtime/checkpoint.py`, classe `ExecutionCheckpoint` |
| `CheckpointStore.save` | Persistir um checkpoint associado a token opaco | `runtime/checkpoint.py`, protocolo `CheckpointStore` |
| `CheckpointStore.consume` | Recuperar e invalidar atomicamente um token de uso único | `runtime/checkpoint.py`, protocolo `CheckpointStore` |
| `ResumeToken` | Capacidade opaca e imprevisível para retomada | `approvals/suspension.py`, classe `ResumeToken` |
| `ExecutionSuspension` | Resultado não terminal que entrega solicitação e token | `approvals/suspension.py`, classe `ExecutionSuspension` |
| `ExecutionStateRestorer` | Criar e restaurar o estado a partir do checkpoint | `runtime/restorer.py`, classe `ExecutionStateRestorer` |

`CheckpointStore` possui somente `save` e `consume`. Não há contratos públicos
de leitura sem consumo, listagem, remoção, renovação de lease ou limpeza.

## Modelo persistido v1

| Campo real | Tipo | Obrigatório | Serialização/restrição |
| --- | --- | --- | --- |
| `checkpoint_version` | `int` | sim | JSON number, maior que zero |
| `execution_id` | `str` | sim | não vazio |
| `execution_mode` | `ExecutionMode` | sim | `run` ou `stream` |
| `agent` | `AgentDefinition` | sim | modelo Pydantic; contém `agent_id` |
| `input_data`, `effective_input` | `AgentInput`, opcional | sim/não | modelos Pydantic |
| `context`, `trace_context` | `AgentContext`, `TraceContext` opcional | sim/não | contexto deve ter o mesmo execution ID |
| `status` | `ExecutionStatus` | sim | somente `waiting_for_approval` |
| `messages`, `knowledge_context` | tupla/modelo opcional | sim/não | JSON de contratos provider-neutral |
| `model_selection`, `usage`, `has_model_usage` | modelos e boolean | sim | estado acumulado do modelo |
| `turn_count`, `tool_call_count` | `int` | sim | não negativos |
| `events`, `transitions` | tuplas | sim | eventos contínuos; transição final coincide com status |
| `tool_call_records`, `guardrail_records` | tuplas | sim | journals serializáveis |
| `pending_approval`, `pending_tool_calls` | modelo/tupla | sim | ao menos uma chamada; identidade coincidente |
| `approval_history` | tupla | sim | default vazio |
| `limits`, `budget` | modelos | sim | políticas preservadas |
| `remaining_timeout_seconds` | `float` opcional | não | finito e não negativo |
| `created_at`, `updated_at` | `datetime` | sim | timezone obrigatório; ordem temporal válida |
| `metadata` | `dict[str, object]` | sim | JSON compatível, default vazio |

Não existem campos próprios `checkpoint_id`, `expires_at` ou `consumed_at`.
`schema_version` é representado pelo nome real `checkpoint_version`.

## Garantias observadas

- I/O assíncrono e injeção do store no runtime.
- Modelos Pydantic imutáveis, com campos extras proibidos.
- `CURRENT_CHECKPOINT_VERSION = 1` e rejeição de versão não suportada.
- Identidades, timestamps, sequência de eventos, transições e chamada pendente
  são validados.
- O token não é incluído no checkpoint.
- Uma suspensão somente é entregue depois de `save` concluído.
- `consume` é normativamente atômico, mas a implementação dessa garantia cabe
  ao adapter.

## Limites da certificação

A certificação não atribui garantia de efeito externo exatamente uma vez. Ela
certifica, no máximo, um consumo bem-sucedido do token quando o adapter cumpre o
protocolo. Falha após o consumo e antes ou durante a ferramenta permanece uma
janela de recuperação não resolvida.

## Evidências executáveis

- `test_checkpoint_store_signature_is_the_certified_minimal_contract`
- `test_checkpoint_field_inventory_matches_the_version_one_baseline`
- `test_checkpoint_v1_json_round_trip_is_deterministic_and_token_free`
- testes HITL em `tests/runtime/test_human_approval.py` e
  `test_human_approval_streaming.py`
