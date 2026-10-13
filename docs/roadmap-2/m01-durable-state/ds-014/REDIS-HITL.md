# HITL com Redis

Redis armazena o checkpoint; PostgreSQL permanece a autoridade da decisão e da
auditoria. O fluxo real cobriu suspensão Redis, rolling update dos workers,
rejeição durável, retomada sem efeito e replay negado.

Topologia certificada: Redis 7.4.5 standalone, AOF `always` e `noeviction`.
Sentinel, Cluster e failover físico permanecem fora do escopo. A durabilidade
continua dependente da configuração operacional declarada.
