# Análise de índices

Ambiente: PostgreSQL 16.14, 10.000 checkpoints e tombstones, 20 amostras por
consulta, `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`.

| Caminho | Índice observado | Mediana ms | p95 ms |
| --- | --- | ---: | ---: |
| lookup | `checkpoints_pkey` | 0,021 | 0,023 |
| consume atômico | `checkpoints_pkey` | 0,027 | 0,037 |
| update otimista | `checkpoints_pkey` | 0,0735 | 0,100 |
| acquire lease | `checkpoint_leases_pkey` | 0,0555 | 0,064 |
| renew lease | `checkpoint_leases_pkey` | 0,055 | 0,073 |
| discovery de recovery | `atlas_checkpoints_recovery_candidates_idx` | 0,0425 | 0,055 |
| classificação de retenção | `atlas_checkpoints_retention_idx` | 0,0465 | 0,154 |
| discovery de purge | `atlas_checkpoints_retention_idx` | 0,0655 | 0,075 |
| lookup de tombstone | `checkpoint_tombstones_pkey` | 0,020 | 0,037 |

O primeiro baseline encontrou sequential scan no discovery de recovery, com
mediana de 2,079 ms. A migration 007 adicionou o índice alinhado ao `ORDER BY`;
o segundo baseline comprovou index scan e redução para 0,0425 ms. Nenhum hint ou
`enable_seqscan=off` foi utilizado.

O script reproduzível é `scripts/benchmark_postgresql_schema.py`; ele exige DSN
explícito, banco terminado em `_test` e confirmação para preparar o dataset.
