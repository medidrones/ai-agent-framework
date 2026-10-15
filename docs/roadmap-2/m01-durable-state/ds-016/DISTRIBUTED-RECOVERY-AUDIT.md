# Auditoria de recuperação distribuída

| Cenário | Mecanismo | Evidência | Resultado |
| --- | --- | --- | --- |
| worker concorrente | lease exclusivo | DS-005/011/012 | PASS |
| owner obsoleto | fencing token monotônico | DS-005/011/013 | PASS |
| crash antes do commit | rollback/estado recuperável | DS-012 | PASS |
| commit de resultado incerto | reconciliação por estado/operação | DS-011/012 | PASS |
| restart do coordenador | tentativas duráveis | DS-006/012 | PASS |
| side effect externo | idempotência/fencing do host | DS-012 | PASS delimitado |
| cancellation/deadline | propagação e cleanup | testes de runtime | PASS |
| HITL pendente | decisão nunca inferida | ADR-006/010 | PASS |

`RECOVERED` significa continuidade confirmada pelo runtime. Não significa que
um sistema externo executou um efeito exatamente uma vez. Essa fronteira está
registrada como limitação, não como garantia omitida.

**Decisão:** `DISTRIBUTED_RECOVERY = VERIFIED`.
