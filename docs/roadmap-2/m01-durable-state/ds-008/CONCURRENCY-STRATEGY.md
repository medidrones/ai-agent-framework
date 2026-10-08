# Estratégia de concorrência

`SKIP LOCKED` distribui linhas entre workers e evita espera longa. O row lock
serializa retenção, legal hold, consumo e delete do checkpoint. O advisory lock
por execução sincroniza tabelas distintas; aquisição, renovação e liberação de
lease adotam a mesma chave antes de alterar ownership.

O purge usa `pg_try_advisory_xact_lock`: diante de lease/recovery concorrente,
bloqueia o candidato em vez de criar espera circular. Testes reais cobrem dois
workers, dois processos, cinco workers no benchmark, purge/lease, purge/resume,
recovery ativo, row lock e fencing.
