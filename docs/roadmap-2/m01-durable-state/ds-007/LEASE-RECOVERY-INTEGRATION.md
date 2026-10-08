# Integração com lease e recovery

O classificador bloqueia registros com lease válido ou tentativa de recovery
incompleta. Fencing permanece obrigatório no consumo leased, e o tombstone
registra apenas o fencing token, sem credenciais ou payload. A descoberta da
DS-006 continua excluindo checkpoints expirados pelo relógio do banco.
