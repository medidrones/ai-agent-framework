# Estratégia de auditoria

A migration 006 cria `checkpoint_purge_audit`. Cada resultado confirmado grava
`purge_run_id`, `operation_id`, digest opaco do checkpoint, execução, tenant,
tipo de registro, outcome, reason code, versão da política e timestamp do banco.

Payload, resume token, credencial e identidade secreta não são persistidos. O
registro participa da mesma transação da mutação. `operation_id` é único e
permite reconciliar commit desconhecido sem repetir exclusão às cegas.
