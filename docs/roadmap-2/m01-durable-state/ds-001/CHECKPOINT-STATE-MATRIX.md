# Matriz de estado do checkpoint

| Grupo | Campos preservados | Invariante relevante |
| --- | --- | --- |
| Identidade | `checkpoint_version`, `execution_id`, `execution_mode` | ID não vazio e modalidade mantida na retomada |
| Definição | `agent`, `input_data`, `effective_input`, `context` | contexto pertence à execução |
| Modelo | `messages`, `model_selection`, `usage`, `has_model_usage` | seleção e uso não são recalculados |
| Lifecycle | `status`, `events`, `transitions` | status deve ser `WAITING_FOR_APPROVAL`; journal contínuo |
| Limites | `turn_count`, `tool_call_count`, `limits`, `budget`, `remaining_timeout_seconds` | contadores não reiniciam; timeout é finito e não negativo |
| Ferramentas | `tool_call_records`, `pending_tool_calls` | primeira chamada corresponde ao assunto da aprovação |
| Aprovação | `pending_approval`, `approval_history` | execução e agente devem coincidir |
| Contexto enriquecido | `knowledge_context`, `guardrail_records`, `trace_context` | fatos concluídos são preservados, não refeitos |
| Temporal | `created_at`, `updated_at` | timezone obrigatório; atualização não antecede criação |
| Extensão | `metadata` | somente estrutura JSON compatível |

## Não persistido deliberadamente

Provider, registry, executor, ferramentas, callbacks, locks, clock, deadline
monotônico absoluto, adapters, credenciais e o próprio `ResumeToken` não fazem
parte do payload.

## Fluxo certificado

```text
EXECUTING_TOOL → WAITING_FOR_TOOL → WAITING_FOR_APPROVAL
  → save concluído → ExecutionSuspension
  → consume atômico → validação/restauração
  → APPROVE: ferramenta e loop | REJECT/expiração: REJECTED
```

O tempo de espera humana não reduz `remaining_timeout_seconds`. Provider,
ferramenta, permissões e limites são revalidados após a restauração.

## Matriz normativa das operações reais

O contrato não modela uma enumeração de estados físicos do registro. Para não
inventá-la, a matriz usa somente as condições observáveis “ausente”,
“disponível” e “consumido/inexistente”.

| Estado inicial real | Operação | Estado final observável | Status | Evidência |
| --- | --- | --- | --- | --- |
| ausente | `save` | disponível | PASS | suspensão só retorna após `save`; fake armazena por token |
| disponível | leitura sem mutação | — | FAIL | operação pública `read` é `MISSING`; `peek` existe apenas no fake de teste |
| disponível | `consume` | consumido/inexistente | PASS | protocolo exige recuperação e invalidação atômicas |
| consumido/inexistente | `consume` | consumido/inexistente | PASS | `CheckpointNotFoundError` no fake e teste de replay |
| aprovação expirada | `consume` | consumido; execução `REJECTED` | PASS | expiração é validada pelo runtime após consumo |

Não existe estado persistido `expired`: a expiração pertence à
`ApprovalRequest`, e não há TTL normativo no store. Não existe estado persistido
`consumed`: o registro deixa de ser recuperável pelo token.
