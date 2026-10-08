# Recuperação PostgreSQL

Certificado com PostgreSQL 16.14 real. Foram validados migrations, transações,
rollback, optimistic concurrency, consumo atômico, tombstones, lease, fencing,
tentativas duráveis, concorrência entre processos e isolamento por tenant.

O probe `scripts/certify_ds012_restart.py` gravou um checkpoint, o container foi
reiniciado e outra execução confirmou o mesmo `execution_id`: `PASS`.

Commit desconhecido nunca autoriza retry direto. A reconciliação consulta o estado
durável; ausência de evidência resulta em bloqueio. Failover/replicação não foram
certificados porque não pertencem à topologia standalone declarada.
