# Trilha de auditoria

A tabela `hitl_audit_events` é separada de logs, métricas e traces. Cada evento
possui ID único, request, execução, tenant, tipo, ator, timestamp e detalhes
não secretos. A ordem é dada por `BIGSERIAL`.

Eventos certificados:

1. `approval.requested`;
2. `approval.decided`;
3. `approval.resumed`.

O evento `approval.decided` participa da mesma transação da mudança de estado.
O scan de evidência confirmou ausência do token bruto na auditoria e nos logs.
