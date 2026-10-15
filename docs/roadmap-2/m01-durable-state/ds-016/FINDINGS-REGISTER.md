# Registro consolidado de findings e limitações

## Findings técnicos

| Severidade | Abertos | Bloqueantes |
| --- | ---: | ---: |
| Critical/P0 | 0 | 0 |
| High/P1 | 0 | 0 |
| Medium | 0 | 0 |
| Low | 0 | 0 |

## Pendência de governança

| ID | Descrição | Estado | Efeito |
| --- | --- | --- | --- |
| GOV-001 | cinco sign-offs humanos específicos da DS-016 | CLOSED | Jorge Medina aprovou os cinco papéis em 15/10/2026 |

## Limitações aceitas do desenho

- não há garantia universal de exactly-once para efeitos externos;
- Redis depende da durabilidade configurada; Cluster/Sentinel não certificados;
- autenticação e autorização do principal pertencem ao host;
- confirmação perdida após commit exige reconciliação;
- resultados de performance são baseline do ambiente certificado, não SLA;
- a evidência Kubernetes da DS-013/014 foi reutilizada, não reexecutada na
  DS-016, pois o comportamento funcional correspondente não mudou.

Essas limitações estão documentadas nas ADRs e não são falhas ocultas. Nenhum
finding técnico ou de governança permanece aberto.
