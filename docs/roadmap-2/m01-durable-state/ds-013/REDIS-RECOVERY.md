# Recovery Redis

Redis 7.4.5 real foi configurado como standalone, AOF `appendfsync always` e
`maxmemory-policy noeviction`, sobre PVC. Foram validados pod crash, restart,
reconexão, HITL aprovado/rejeitado, concorrência e replay. O restart medido foi
aproximadamente 1,5 s, com contador de efeito igual a `1`.

O resultado é `VERIFIED_WITH_DECLARED_LIMITS`: não certifica Sentinel, Cluster,
replicação, failover físico nem equivalência de durabilidade ao PostgreSQL.
Ausência inesperada de chave não autoriza reconstrução arbitrária.
