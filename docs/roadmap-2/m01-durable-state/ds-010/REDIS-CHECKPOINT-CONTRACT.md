# Contrato de checkpoint Redis

| Operação | Garantia |
| --- | --- |
| `save` | cria somente quando chave/tombstone não existe |
| `read` | retorna somente checkpoint ativo e não expirado |
| `compare_and_swap` | atualiza somente a revisão esperada |
| `consume` | um vencedor, tombstone sem payload |
| `consume_authorized` | valida antes e consome a mesma revisão/digest |

O ponto de linearização é a execução do script Lua no Redis. `TIME` do servidor
define a fronteira `agora >= expires_at`. Ausência, expiração e replay usam a
semântica pública de `CheckpointNotFoundError`.

Não há alegação de exactly-once para efeitos externos. Falha de transporte após
o comando pode gerar `RedisCheckpointOutcomeUnknownError`; o chamador deve
reconciliar antes de tentar novamente.
