# Matriz de requisitos e evidências

| Gate | Requisito | Evidência verificável | Estado |
| --- | --- | --- | --- |
| G01 | DS-015 certificada | `../ds-015/CERTIFICATION-REPORT.md` | PASS |
| G02 | rastreabilidade DS-001–015 | `TASK-TRACEABILITY-MATRIX.md` | PASS |
| G03 | integridade das evidências | histórico Git e relatórios versionados | PASS |
| G04 | arquitetura | `ARCHITECTURE-AUDIT.md` | PASS |
| G05 | independência do core | testes de arquitetura e manifests | PASS |
| G06 | contratos de checkpoint | `CHECKPOINT-CONTRACT-AUDIT.md` | PASS |
| G07 | serialização | fixtures e testes de compatibilidade | PASS |
| G08 | consumo atômico | DS-002/004/010/011 e integração real | PASS |
| G09 | concorrência otimista | DS-003 e integração PostgreSQL | PASS |
| G10 | PostgreSQL | `POSTGRESQL-CERTIFICATION.md` | PASS |
| G11 | Redis com limites declarados | `REDIS-CERTIFICATION.md` | PASS |
| G12 | leases | DS-005/011 | PASS |
| G13 | fencing | DS-005/011/013 | PASS |
| G14 | recovery coordinator | DS-006/012 | PASS |
| G15 | crash consistency | DS-012 | PASS |
| G16 | Kubernetes | `KUBERNETES-CERTIFICATION.md` | PASS |
| G17 | HITL durável | `DURABLE-HITL-CERTIFICATION.md` | PASS |
| G18 | autorização de aprovação | ADR-010 e DS-014 | PASS |
| G19 | segurança de resume tokens | DS-014 e testes | PASS |
| G20 | proteção contra replay | tombstones, consumo atômico e testes | PASS |
| G21 | reconciliação de efeitos | DS-012, garantia delimitada | PASS |
| G22 | expiração e retenção | DS-007/008 | PASS |
| G23 | segurança | `SECURITY-AUDIT.md` | PASS |
| G24 | isolamento por tenant | DS-014 e testes negativos | PASS |
| G25 | thresholds de performance | `PERFORMANCE-CERTIFICATION.md` | PASS |
| G26 | soak e estabilidade | DS-015, dois ensaios de 60 min | PASS |
| G27 | compatibilidade retroativa | `COMPATIBILITY-AUDIT.md` | PASS |
| G28 | quality gates | `QUALITY-GATES.md` | PASS |
| G29 | packaging e instalação limpa | 14 artefatos e três venvs | PASS |
| G30 | documentação e findings | 19 artefatos e registro consolidado | PASS |
| G31 | cinco owner sign-offs | Jorge Medina, cinco papéis, `SIGN-OFF-RECORD.md` | PASS |
| G32 | aprovação final para release | G01–G31 aprovados; P0/P1 = 0 | PASS |

Resultado técnico: **30/30 gates técnicos PASS**. Resultado global:
**32/32 gates PASS**.
