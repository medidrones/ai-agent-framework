# Arquitetura da DS-009

## Escopo

A DS-009 certifica o schema relacional produzido pelas DS-002 a DS-008 e
adiciona somente dois mecanismos de hardening: a migration aditiva 007 e o
verificador explícito, tipado e somente leitura. O core não conhece PostgreSQL;
toda a implementação permanece no pacote opcional `atlas-agent-adapters`.

```text
aplicação
  ├── PostgreSQLCheckpointMigrator (operação administrativa explícita)
  │     ├── advisory transaction lock
  │     ├── histórico + SHA-256
  │     └── migrations imutáveis 001..007
  ├── PostgreSQLSchemaCompatibilityChecker (readiness somente leitura)
  │     ├── histórico
  │     ├── colunas/tipos/nulabilidade
  │     ├── constraints
  │     └── índices
  └── adapters de checkpoint/lease/recovery/retention/purge
          └── schema atlas_agent
```

O checker não cria schema, não aplica migration, não repara drift e não lê
payloads. O migrator só é executado por chamada explícita e usa o pool entregue
pelo chamador. A revisão 007 cria o índice de ordenação dos candidatos de
recovery sem alterar formato persistido, contrato público ou dependências do
core.

## Invariantes

- migrations aplicadas são imutáveis e verificadas por checksum;
- versões desconhecidas, lacunas e downgrade implícito são bloqueados;
- toda revisão é aplicada na mesma transação do registro de histórico;
- dois runners são serializados por `pg_advisory_xact_lock(4283002)`;
- versões 6 e 7 podem coexistir durante a expansão 007;
- o runtime funciona sem privilégios DDL;
- schema incompatível nunca é reparado automaticamente.

## Rastreabilidade

| Origem | Contrato | Objetos principais | Revisão | Evidência |
| --- | --- | --- | --- | --- |
| DS-001 | `CheckpointStore` | formato JSONB e identidade | 001 | fixture v1 e regressão core |
| DS-002 | `PostgreSQLCheckpointStore` | `checkpoints` | 001 | integração save/read/consume |
| DS-003 | concorrência otimista | `revision`, `modified_at` | 002 | conflitos e corrida CAS |
| DS-004 | resume atômico | `checkpoints`, `checkpoint_tombstones` | 001/005 | consumo único e replay |
| DS-005 | lease/ownership | `checkpoint_leases` | 003 | ownership e fencing |
| DS-006 | recovery | `execution_recovery_attempts` e índice de candidatos | 004/007 | recovery e ordenação |
| DS-007 | retenção | metadados, tombstones e índices | 005 | TTL/legal retention |
| DS-008 | purge | `checkpoint_purge_audit`, `legal_hold` | 006 | purge transacional |

Nenhuma relação física foi adicionada entre agregados com ciclos de retenção
independentes; a decisão está detalhada em `REFERENTIAL-INTEGRITY.md`.
