# Matriz de falhas

| Falha | Comportamento |
| --- | --- |
| Redis indisponível/timeout | `RedisCheckpointStoreError`, sem segredo |
| Resposta perdida no consumo | reconciliação por receipt; outcome unknown tipado |
| Payload corrompido | `InvalidCheckpointError`, sem consumo autorizado |
| Schema desconhecido | `UnsupportedCheckpointVersionError` |
| Revisão obsoleta | conflito tipado, sem overwrite |
| Token consumido/expirado | `CheckpointNotFoundError` |
| Cancelamento | `CancelledError` propagado |
| Cliente injetado | não fechado |
| Cliente criado por `from_url` | fechado uma única vez |
| Falha de observabilidade | runtime preserva resultado funcional |

Operações não idempotentes não recebem retry automático. A mensagem pública não
inclui URL, credencial, token, chave ou payload.
