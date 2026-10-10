# Evidências de teste

Baseline: `2b47559c90df8423d7f5fb3c68f1ee08b2980529`. Imagem final:
`sha256:746ae736c3f682295f9b3f4e78e117033798287293e69ffb07ee8c61cc26a713`,
UID `10001:10001`, 180.578.972 bytes.

| Evidência | Resultado |
| --- | --- |
| Certificação Kubernetes real | exit code 0 |
| DS013-T01–T50 | PASS, conforme matriz e cenários agrupados |
| Efeitos externos | aprovados = 1; rejeitado = 0 |
| RBAC | 5/5 operações negadas |
| NetworkPolicy | pod sem rótulo bloqueado; runner permitido |
| Tenant isolation | 0 tentativa para `tenant-other` |
| PostgreSQL/Redis reais | 121 testes de integração PASS |
| Suíte completa com backends reais | 1.414 PASS, 0 FAIL, 0 SKIP |
| Testes unitários do host | 6 PASS |
| Cobertura do monorepo | 92,68% com branches |
| Ruff | PASS; 739 arquivos formatados |
| mypy | PASS; 381 arquivos fonte |
| Builds | core, adapters e host: wheel + sdist PASS |
| Manifest validation | todos aceitos pelo API server |
| Secret scan em logs/image metadata | PASS |

Os arquivos brutos da última execução ficam em `build/ds013/evidence/` até o
cleanup do workspace. A execução é reproduzível pelos scripts versionados; os
relatórios preservam os resultados sanitizados sem credenciais.
