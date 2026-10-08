# Elegibilidade de purge

| Condição revalidada | Resultado |
| --- | --- |
| retenção vencida, sem guard | `PURGED` |
| dry-run elegível | `SKIPPED/dry_run_eligible` |
| checkpoint ainda ativo | `SKIPPED/checkpoint_active` |
| retenção vigente | `BLOCKED/retention_active` |
| lease vigente | `BLOCKED/active_lease` |
| recovery incompleto | `BLOCKED/active_recovery` |
| legal hold | `BLOCKED/legal_hold` |
| schema ou política incompatível | `BLOCKED/incompatible_checkpoint` |
| outra operação detém lock da execução | `BLOCKED/concurrent_operation` |

A descoberta considera apenas prazos potencialmente vencidos. A decisão final
é refeita dentro da transação usando o relógio do PostgreSQL e o classificador
da DS-007. Falhas de interpretação são fail-closed.
