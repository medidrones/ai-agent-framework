# Semântica transacional

Uma transação de lote executa:

1. `statement_timeout` e `lock_timeout` locais;
2. seleção limitada e ordenada com `FOR UPDATE SKIP LOCKED`;
3. `pg_try_advisory_xact_lock` por `execution_id`;
4. leitura de lease, recovery e relógio autoritativo;
5. reclassificação DS-007;
6. criação/expansão de tombstone e preservação de fencing;
7. exclusão física condicionada;
8. inserção da auditoria;
9. commit.

Falha de tombstone, delete ou auditoria aborta todo o lote. A resposta só é
construída como `PURGED` após sair com sucesso do contexto transacional. Em
falha no commit, `operation_id` e `purge_run_id` reconciliam a auditoria.
