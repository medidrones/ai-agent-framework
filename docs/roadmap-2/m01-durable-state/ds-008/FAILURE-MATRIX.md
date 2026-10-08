# Matriz de falhas

| Falha | Comportamento comprovado |
| --- | --- |
| antes do commit | rollback integral |
| tombstone/auditoria | checkpoint preservado |
| commit sem confirmação | reconciliação; ausência vira `OUTCOME_UNKNOWN` |
| PostgreSQL/pool | erro controlado do adapter |
| deadlock/lock timeout | sem confirmação falsa; transação abortada |
| linha bloqueada | `SKIP LOCKED`, sem exclusão |
| cancellation | `CancelledError` propagado e rollback |
| schema/política desconhecida | bloqueio fail-closed |
| observabilidade indisponível | resultado funcional preservado |

Retry deve partir do estado durável e jamais inferir rollback pela ausência de
resposta do cliente.
