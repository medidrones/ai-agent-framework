# Persistência e recuperação Redis

Certificação executada com Redis 7.4.11 standalone:

- AOF habilitado;
- `appendfsync always`;
- política `noeviction`;
- reinicialização controlada do container;
- save antes do restart, read e consumo depois do restart.

O restart do processo Python também foi validado com duas instâncias do store e
do runtime. RDB foi observado como habilitado pelo servidor, mas não recebeu
certificação isolada de janela de perda. Sentinel, Cluster, replicação e failover
ficam fora da matriz oficial.

ACK de escrita não garante, por si só, disco ou réplica. Deployments críticos
devem definir AOF/RDB, fsync, replicação, backup, memória e `noeviction` segundo
seu RPO/RTO. Eviction não deve ser interpretada como expiração legítima.
