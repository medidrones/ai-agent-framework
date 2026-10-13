# Matriz de estados de aprovação

| Estado | Comando permitido | Próximo estado | Observação |
| --- | --- | --- | --- |
| `pending` | decisão válida | `approved`/`rejected` | um vencedor |
| `pending` | expiração | `expired` lógico | retomada negada |
| `approved` | mesmo `decision_id` | `approved` | retry idempotente |
| `rejected` | mesmo `decision_id` | `rejected` | retry idempotente |
| decidido | decisão diferente | sem mudança | conflito |
| decidido | retomada confirmada | `resumed` | resultado auditado |
| `resumed` | mesmo resultado | `resumed` | retry idempotente |
| `resumed` | outro resultado | sem mudança | conflito |

Checkpoint desconhecido, expirado ou consumido permanece não reativável. A
rejeição encerra o fluxo sem executar a ferramenta.
