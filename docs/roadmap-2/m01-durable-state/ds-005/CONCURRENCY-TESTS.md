# Testes de concorrência

Os testes usam PostgreSQL 16 real e conexões independentes. A suíte cobre:

- duas aquisições concorrentes com exatamente um vencedor;
- exclusividade entre owners;
- expiração, readquisição e token estritamente crescente;
- renew concorrente sem regressão de expiração;
- release, double release e gerações obsoletas;
- dois processos Windows criados com `spawn`;
- CAS DS-003 com lease válido, revisão obsoleta e stale owner;
- consumo DS-004 com fencing, rollback e checkpoint consumido;
- cancelamento e falha de conexão.

Arquivo executável: `packages/atlas-agent-adapters/tests/test_postgresql_checkpoint_lease.py`.
