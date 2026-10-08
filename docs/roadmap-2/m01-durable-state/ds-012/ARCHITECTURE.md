# Arquitetura de recuperação de falhas

A DS-012 mantém a inversão de dependência: o core classifica segurança e coordena
recovery; PostgreSQL e Redis implementam persistência. O host continua responsável
por identidade, autorização, agendamento e topologia.

```text
Host -> ExecutionRecoveryCoordinator -> contratos do core
                         |-> CheckpointStore / LeaseManager
                         |-> RecoveryAttemptRecorder
                         |-> RecoverySafetyPolicy
                         `-> AgentRuntime.resume[_stream]
```

`runtime/failure_recovery.py` adiciona uma taxonomia neutra e uma política
fail-closed. Não altera `AgentRuntime`, não cria scheduler e não introduz dependência
de infraestrutura no core. `runtime/recovery.py` conserva discovery limitado,
revalidação após lease, fencing, timeout, cancellation e tentativas persistentes.

Evidências: `test_failure_recovery.py`, `test_recovery.py`,
`test_postgresql_execution_recovery.py` e `test_redis_hitl_integration.py`.
