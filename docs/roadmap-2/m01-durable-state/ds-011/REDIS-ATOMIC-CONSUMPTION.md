# Consumo atômico Redis

`CONSUME_SCRIPT` e `CONSUME_LEASED_SCRIPT` validam existência, schema, estado,
expiração pelo relógio Redis, revisão e digest antes de alterar o registro.
Quando há lease, também validam execution ID, owner, fencing token e validade.

O script vencedor grava `state=consumed`, `consumed_at_ms`, retenção e o
`consume_operation_id`; depois remove payload e digest e preserva o tombstone.
Tentativas posteriores observam estado não ativo e são rejeitadas.

Invariante comprovada com 10 processos e com 100 coroutines:

```text
successful_consumptions = 1
rejected_consumptions = N - 1
```
