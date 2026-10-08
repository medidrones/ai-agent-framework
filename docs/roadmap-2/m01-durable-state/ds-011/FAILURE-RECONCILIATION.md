# Reconciliação de falhas

Falha antes do envio deixa o checkpoint disponível. Falha depois da execução
pode perder a resposta; por isso, o adapter consulta o receipt durável pelo
mesmo `operation_id`. Se a consulta também falhar, lança
`RedisCheckpointOutcomeUnknownError` e bloqueia retry cego.

`asyncio.CancelledError` não é capturado. Timeout não é interpretado como
rollback. Scripts validam todas as condições antes da mutação para evitar estado
parcial produzido por erro de validação.

Restart foi validado com AOF `appendfsync always`. Failover depende da topologia
e não foi declarado nesta matriz.
