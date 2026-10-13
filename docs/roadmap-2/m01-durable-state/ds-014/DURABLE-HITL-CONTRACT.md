# Contrato HITL durável

Uma suspensão válida preserva `execution_id`, `approval_request_id`, agente,
chamada de ferramenta, timestamps e token opaco. O registro durável acrescenta
tenant, backend, digest HMAC, revisão e lifecycle da decisão sem modificar os
modelos públicos do Atlas 1.x.

Garantias certificadas:

- suspensão antes de qualquer efeito da ferramenta;
- decisão humana explícita `approve` ou `reject`;
- binding integral do escopo;
- no máximo uma decisão conflitante vencedora;
- retry idempotente pelo mesmo `decision_id`;
- consumo único do checkpoint;
- decisão e auditoria na mesma transação PostgreSQL;
- retomada reconciliável depois de resultado ambíguo.

Fora do contrato: autenticação de usuário, UI, exactly-once universal e transação
distribuída com sistemas externos.
