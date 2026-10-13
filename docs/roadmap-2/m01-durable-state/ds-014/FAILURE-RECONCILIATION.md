# Falhas e reconciliação

| Janela | Estado durável | Ação segura |
| --- | --- | --- |
| antes da decisão | `pending` | repetir decisão |
| após decisão, antes de resume | decidido | repetir mesmo `decision_id` |
| durante consumo | decidido | reconciliar token/tombstone |
| após consumo, antes do resultado | decidido | classificar `OUTCOME_UNKNOWN` |
| após resultado | `resumed` | retry idempotente |

Falha de auditoria reverte a decisão. Falha de telemetria não altera a decisão.
Efeito externo somente pode ser repetido quando possuir chave idempotente ou
reconciliação confiável. Caso contrário, o host bloqueia em vez de alegar
exactly-once.
