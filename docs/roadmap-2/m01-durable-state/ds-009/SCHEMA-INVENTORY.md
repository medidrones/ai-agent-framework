# Inventário do schema PostgreSQL

Schema certificado: `atlas_agent`, revisão 7.

## Tabelas

| Tabela | Chave | Colunas funcionais | Origem |
| --- | --- | --- | --- |
| `schema_migrations` | `(component, version)` | `checksum`, `applied_at` | bootstrap |
| `checkpoints` | `token_digest` | versão, execução, agente, tenant, JSONB, timestamps, revisão, retenção, legal hold | 001/002/005/006 |
| `checkpoint_leases` | `checkpoint_id` | owner, fencing token, aquisição, expiração | 003 |
| `execution_recovery_attempts` | `attempt_id` | execução, checkpoint, owner, fencing, tentativa, conclusão, outcome, retenção | 004/005 |
| `checkpoint_tombstones` | `token_digest` | execução, agente, tenant, consumo, retenção, fencing, legal hold | 005/006 |
| `checkpoint_purge_audit` | `audit_id` | run/operação, checkpoint, execução, tenant, tipo, outcome, razão, política, data | 006 |

O manifesto executável em `schema.py` certifica 56 colunas com tipo PostgreSQL
(`bytea`, `int4`, `int8`, `text`, `jsonb`, `timestamptz`, `uuid`, `bool`) e
nulabilidade. A ausência ou incompatibilidade de qualquer coluna obrigatória
produz `SCHEMA_DRIFT_DETECTED`.

## Constraints

- seis chaves primárias;
- unicidade `(execution_id, checkpoint_id, attempt_number)` em recovery;
- unicidade de `operation_id` na auditoria de purge;
- checks de versão/revisão, ordem temporal, estado de lease, fencing,
  completion, classe de retenção, tipo e outcome de purge.

Não existem sequences, triggers, views, procedures nem foreign keys. UUIDs e
IDs são produzidos pela aplicação; timestamps possuem defaults explícitos.

## Índices explícitos

- checkpoints: execução, tenant parcial, expiração parcial, retenção, candidatos
  de purge e candidatos de recovery;
- leases: expiração parcial;
- recovery: `(execution_id, checkpoint_id, attempt_number DESC)`;
- tombstones: retenção, tenant parcial e candidatos de purge;
- auditoria: run/operação e tenant/data parcial.

Os índices automáticos de PK/UNIQUE complementam esse conjunto. O catálogo real
foi comparado ao manifesto pelo checker após instalação vazia.
