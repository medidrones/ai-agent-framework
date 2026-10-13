# HITL com PostgreSQL

O schema aditivo do host contém `hitl_approvals` e `hitl_audit_events`. A decisão
e seu evento são gravados na mesma transação. Um trigger de fault injection
forçou falha da auditoria e comprovou rollback da decisão para `pending`.

O fluxo real cobriu suspensão, troca de pod, decisão, retomada, efeito único,
replay negado e auditoria. PostgreSQL 16.10 foi executado em container local e
no cluster kind.
