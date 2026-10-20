# Integração futura com Durable State

O M01 oferece primitives certificadas de checkpoints, consumo atômico, leases,
fencing, recovery, retenção e purge. Workflows deverão reutilizar essas
capacidades por composição e adapters opcionais.

A OR-001 não persiste workflows e não altera `CheckpointStore`. Um futuro
checkpoint de workflow precisará distinguir estado do grafo, tentativas de nó e
execuções individuais, preservando a regra de não declarar exactly-once para
efeitos externos.
