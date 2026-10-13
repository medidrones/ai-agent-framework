# Matriz de workloads

| ID | Workload | PostgreSQL | Redis | Evidência principal |
| --- | --- | --- | --- | --- |
| W01 | Checkpoint save | aplicável | aplicável | runner DS-015 |
| W02 | Checkpoint read | aplicável | aplicável | runner DS-015 |
| W03 | Optimistic update | aplicável | aplicável | runner DS-015 |
| W04 | Atomic consume | aplicável | aplicável | runner DS-015 |
| W05 | Lease acquire | aplicável | aplicável | runner DS-015 |
| W06 | Lease renew | aplicável | aplicável | runner DS-015 |
| W07 | Lease release | aplicável | aplicável | runner DS-015 |
| W08 | Recovery discovery | aplicável | não aplicável isoladamente | benchmark DS-012 |
| W09 | Execution recovery | aplicável | composição declarada | DS-012/DS-013 |
| W10 | HITL suspension | aplicável | aplicável | DS-014 e stress HITL |
| W11 | HITL resume | aplicável | aplicável | DS-014 e stress HITL |
| W12 | Retention classification | aplicável | TTL nativo, sem repository equivalente | DS-007/DS-009 |
| W13 | Purge | aplicável | expiração/retention do adapter | DS-008/DS-010 |
| W14 | Mixed workload | aplicável | aplicável | runner DS-015 |
| W15 | Failure recovery | aplicável | conforme AOF standalone | fault injection |

## Payloads

| Perfil | Bytes |
| --- | ---: |
| small | 1.024 |
| medium | 16.384 |
| large | 262.144 |
| extra large | 1.048.576 |

## Concorrência

Os perfis 1–250 formam a faixa operacional avaliada. O perfil 500 é
exploratório e identifica saturação controlada. Uma falha de threshold nesse
perfil não é ocultada nem convertida em promessa de capacidade; o limite
observado é registrado na análise de escalabilidade.

Os testes de contenção exigem exatamente um vencedor e `N-1` rejeições
controladas para consumo, optimistic update e lease.
