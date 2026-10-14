# Soak test

Cada backend é executado separadamente por 3.600 segundos com 50 workers e
workload contínuo de save, read e consume. O relógio monotônico do processo
controla a duração; não há equivalência entre execuções curtas e o gate final.

São medidos:

- ciclos concluídos e falhas inesperadas;
- mediana, p95, p99 e throughput;
- CPU consumida pelo processo;
- memória atual e pico por `tracemalloc`;
- crescimento líquido de memória;
- tarefas assíncronas remanescentes após cleanup.

O gate exige duração completa, zero falha inesperada, p95/p99 dentro dos
thresholds, crescimento de memória de até 64 MiB e zero tarefa órfã.

Os valores efetivamente medidos são preservados nos resultados JSON e
consolidados no relatório final.
