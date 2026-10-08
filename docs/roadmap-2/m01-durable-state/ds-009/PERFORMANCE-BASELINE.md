# Baseline de performance

- PostgreSQL: 16.14 Alpine, 64 bits;
- dataset: 10.000 checkpoints, 10.000 leases e 10.000 tombstones;
- amostras: 20 por consulta;
- medição: `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`;
- ambiente: container local de certificação, não produção.

| Query | Mediana ms | p95 ms | Índice |
| --- | ---: | ---: | --- |
| checkpoint lookup | 0,021 | 0,023 | PK checkpoint |
| atomic consume | 0,027 | 0,037 | PK checkpoint |
| optimistic update | 0,0735 | 0,100 | PK checkpoint |
| lease acquisition | 0,0555 | 0,064 | PK lease |
| lease renewal | 0,055 | 0,073 | PK lease |
| recovery discovery | 0,0425 | 0,055 | migration 007 |
| retention classification | 0,0465 | 0,154 | retention |
| purge discovery | 0,0655 | 0,075 | retention |
| tombstone lookup | 0,020 | 0,037 | PK tombstone |

O baseline inicial do recovery foi 2,079 ms/p95 2,261 ms com sequential scan;
a revisão 007 removeu o gap. Resultados são indicativos para regressão local e
não constituem SLA. O benchmark não usa produção nem desabilita seq scan.
