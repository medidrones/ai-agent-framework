# Matriz de elegibilidade

| Situação | Resultado |
| --- | --- |
| Estado terminal | `SKIPPED / terminal` |
| HITL sem decisão real | `SKIPPED / awaiting_approval` |
| HITL com aprovação válida | elegível após revalidação |
| HITL rejeitado | `SKIPPED / not_eligible` |
| Modalidade sem invoker seguro | `BLOCKED / unsupported` |
| Checkpoint inválido | `BLOCKED / invalid_checkpoint` |
| Versão incompatível | `BLOCKED / unsupported_checkpoint_version` |
| Checkpoint ausente/consumido | `SKIPPED / checkpoint_missing` |
| Lease de outro owner | `CONFLICT / lease_conflict` |
| Fencing obsoleto | `CONFLICT / lease_lost` |
| Limite durável atingido | `BLOCKED / attempt_limit_reached` |

A policy oficial conservadora nunca retoma HITL. A policy
`AuthorizedHITLRecoveryPolicy` somente libera o pós-check quando o resolver
fornece uma decisão externa de aprovação. A elegibilidade é avaliada antes e
depois do lease.
