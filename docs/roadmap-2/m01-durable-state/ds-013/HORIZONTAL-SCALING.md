# Escalabilidade horizontal

Foram executados scale out de 2 para 3 réplicas e scale in para 1 e 2 réplicas,
inclusive com checkpoints pendentes. Workers mantiveram memória independente;
PostgreSQL admitiu um owner sob lease/fencing e Redis realizou um consumo
atômico. Os efeitos finais permaneceram únicos.

Baseline local: scale out 5.893,792 ms; scale in 159,543 ms. Esses números são
observações do ambiente `kind`, não SLA.
