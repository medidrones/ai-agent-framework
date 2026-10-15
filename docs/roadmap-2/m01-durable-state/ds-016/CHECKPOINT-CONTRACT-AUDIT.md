# Auditoria dos contratos de checkpoint

Os contratos públicos permanecem provider-neutral e compatíveis com Atlas 1.x.
`CheckpointStore.save()` continua create-only e `consume()` continua destrutivo.
Capabilities de CAS, consumo autorizado, leases e fencing são aditivas.

| Garantia | PostgreSQL | Redis | Resultado |
| --- | --- | --- | --- |
| token opaco/verificador persistido | HMAC/SHA-256 | HMAC/SHA-256 | PASS |
| um consumidor vencedor | `DELETE ... RETURNING` | Lua em uma chave | PASS |
| rollback antes do commit | transação | script atômico | PASS |
| replay rejeitado | tombstone/ausência indistinguível | estado/tombstone | PASS |
| CAS | revisão SQL | revisão no hash | PASS |
| lease e fencing | relógio/lock PostgreSQL | relógio/script Redis | PASS |
| serialização versionada | fixtures 1.0.1 | fixtures 1.0.1 | PASS |
| payload não exposto | erros/logs saneados | erros/logs saneados | PASS |

Os pontos de linearização estão documentados nas ADR-002, ADR-004 e ADR-009.
Cancelamento antes da confirmação não produz falso sucesso. Resposta perdida
após commit é tratada como resultado ambíguo e exige reconciliação.

**Decisão:** `CHECKPOINT_CONTRACTS = VERIFIED`.
