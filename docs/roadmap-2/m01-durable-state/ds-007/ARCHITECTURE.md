# Arquitetura da DS-007

O fluxo é `política do host → contrato do core → fatos persistidos → relógio
PostgreSQL → classificador puro`. O `PostgreSQLCheckpointStore` aplica TTL no
save/CAS e cria tombstone no consumo. O
`PostgreSQLCheckpointRetentionRepository` lê checkpoints e tombstones em lote,
com ordem estável e isolamento por tenant, e não executa `DELETE`.

As dependências continuam apontando do adapter para o core. A API 1.x permanece
aditiva: `retention_policy` é opcional e `retention` legado continua suportado.
