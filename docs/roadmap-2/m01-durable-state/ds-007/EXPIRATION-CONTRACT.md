# Contrato de expiração

- TTLs são positivos, explícitos e versionados.
- O prazo HITL é o menor entre o prazo da aprovação e o TTL da política.
- PostgreSQL decide o instante efetivo com `clock_timestamp()`.
- `agora >= expires_at` significa expirado.
- leitura, CAS, consumo e recovery rejeitam registros expirados.
- expiração lógica não remove o registro nem seu tombstone.
