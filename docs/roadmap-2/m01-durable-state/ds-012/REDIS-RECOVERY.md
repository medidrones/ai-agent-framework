# Recuperação Redis

Certificado com Redis 7.4.11 real, standalone, AOF habilitado,
`appendfsync=always` e `maxmemory-policy=noeviction`.

O probe de restart confirmou checkpoint após reinício do servidor. Scripts Lua
preservam consumo atômico, CAS, lease/fencing e tombstone. Operações identificadas
usam `reconcile_consumption`: `APPLIED`, `NOT_APPLIED`, `AVAILABLE` ou `UNKNOWN`.
`UNKNOWN` permanece bloqueado.

Limites declarados: não há garantia universal contra perda física, failover de
Sentinel/Cluster não foi certificado e configurações RDB/AOF diferentes alteram a
janela de durabilidade. Dado ausente não é inventado nem tratado como expirado.
