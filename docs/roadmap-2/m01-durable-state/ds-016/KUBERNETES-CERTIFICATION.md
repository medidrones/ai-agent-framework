# Certificação consolidada Kubernetes

A evidência operacional real foi produzida na DS-013 e ampliada na DS-014 em
`kind` v0.33.0, Kubernetes cliente/servidor v1.31.2 e Calico 3.31.7. O candidato
da DS-016 não alterou o comportamento certificado após essas tarefas; DS-015 e
os commits de estabilização alteraram instrumentação/testes.

| Cenário | Evidência | Resultado |
| --- | --- | --- |
| pod kill/container restart | `../ds-013/FAULT-INJECTION.md` | PASS |
| graceful shutdown | `../ds-013/GRACEFUL-SHUTDOWN.md` | PASS |
| rolling deployment | `../ds-013/ROLLING-DEPLOYMENT.md` | PASS |
| scale out/in | `../ds-013/HORIZONTAL-SCALING.md` | PASS |
| perda de rede | `../ds-013/NETWORK-FAILURE.md` | PASS |
| leases/fencing | `../ds-013/LEASE-FENCING.md` | PASS |
| HITL distribuído | `../ds-014/KUBERNETES-HITL.md` | PASS |
| 100 decisões concorrentes | `../ds-014/ATOMIC-RESUME.md` | PASS |

A DS-016 referencia a execução versionada e não a apresenta como nova execução
de cluster. Os testes de host e os contratos subjacentes foram reexecutados na
suíte de 1.455 testes.

**Decisão:** `KUBERNETES_RECOVERY = VERIFIED`.
