# Baseline de performance

## Ambiente observado

- PostgreSQL 16 Alpine em container local;
- Windows host;
- pool assíncrono Psycopg;
- 25 checkpoints previamente persistidos;
- 25 consumos autorizados disparados concorrentemente.

## Resultado

Em 2026-10-08, o cenário de chamada do pytest concluiu em aproximadamente
**0,15 segundo**. O teste impõe apenas um limite de sanidade de 30 segundos para
detectar bloqueio ou deadlock.

Este número é uma evidência funcional local, não um SLA nem benchmark de
produção. Latência de rede, tamanho do payload, configuração do pool, WAL,
replicação e contenção alteram o resultado. A propriedade certificada é ausência
de deadlock e conclusão limitada, não uma taxa mínima de throughput.
