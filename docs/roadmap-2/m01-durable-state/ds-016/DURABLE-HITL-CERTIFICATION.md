# Certificação consolidada de HITL durável

| Garantia | Evidência | Resultado |
| --- | --- | --- |
| identidade confiável injetada pelo host | ADR-010 e DS-014 | PASS |
| escopo tenant/execution/request/tool | testes negativos e integração | PASS |
| aprovação/rejeição duráveis | PostgreSQL boundary | PASS |
| token bruto não persistido/logado | HMAC e auditoria de artefatos | PASS |
| uma decisão concorrente | 100 comandos, 1 vencedor | PASS |
| retry idempotente | `decision_id` | PASS |
| decisão conflitante | fail closed | PASS |
| resume atômico | stores certificados | PASS |
| restart entre decisão e resume | decisão reconciliável | PASS |
| trilha de auditoria | request/decision/resume | PASS |

Na revalidação local, os cenários unitários e de integração PostgreSQL/Redis da
DS-014 passaram sem skips. A autenticação continua responsabilidade da aplicação
hospedeira; o Atlas recebe uma identidade já autenticada.

**Decisão:** `DURABLE_HITL = VERIFIED`.
