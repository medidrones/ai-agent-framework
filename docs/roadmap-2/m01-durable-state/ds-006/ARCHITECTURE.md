# Arquitetura DS-006

```text
Recovery Host
    │ chamada explícita e finita
    ▼
ExecutionRecoveryCoordinator
    ├── RecoveryCandidateRepository
    ├── RecoveryEligibilityPolicy
    ├── CheckpointLeaseManager
    ├── RecoveryAttemptRecorder
    ├── ExecutionStateRestorer
    ├── ExecutionRecoveryInvoker
    └── ObservabilityManager
             │
             ▼
       AgentRuntime.resume(..., lease=lease)
             │
             ▼
 PostgreSQL: checkpoint + lease/fencing + tentativa
```

O coordinator não é scheduler nem um segundo runtime. Ele executa um lote
limitado, sequencial e determinístico quando o host chama `recover_once()`.
Todas as dependências são injetadas. Contratos e modelos permanecem no core;
SQL e pools estão apenas em `atlas-agent-adapters`.

O fluxo por candidato é: precheck, aquisição de ownership, admissão durável da
tentativa, leitura autoritativa, restauração, revalidação, continuidade pública,
registro do resultado e release. Falhas de um candidato não interrompem o
restante do lote; cancelamento do consumidor é propagado.
