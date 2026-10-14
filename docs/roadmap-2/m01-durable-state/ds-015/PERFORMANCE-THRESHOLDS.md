# Thresholds de certificação

Estes thresholds foram fixados no runner antes da primeira medição de
certificação. Eles não são SLOs de produção.

| Indicador | Threshold |
| --- | ---: |
| p95 por operação/ciclo na faixa operacional | ≤ 1.000 ms |
| p99 por operação/ciclo na faixa operacional | ≤ 2.000 ms |
| throughput mínimo | ≥ 5 operações/s |
| erro funcional inesperado | 0% |
| crescimento de memória no soak | ≤ 64 MiB |
| tarefas assíncronas órfãs após cleanup | 0 |
| consumo duplicado | 0 |
| lost updates | 0 |
| stale owner writes | 0 |
| violações de tenant | 0 |
| execução de ferramenta não autorizada | 0 |
| purge não autorizado | 0 |
| retry inseguro de efeito externo | 0 |
| vazamento de segredo | 0 |

## Interpretação do perfil extreme

O perfil de 500 workers é um teste de saturação, não uma capacidade prometida.
Se ele ultrapassar p95/p99 sem erro funcional ou violação de integridade, o
ponto é registrado como limite observado. Os thresholds de aprovação se aplicam
à faixa operacional certificada de 1–250 workers e aos workloads isolados.

## Soak

O soak somente passa com 3.600 segundos completos, 50 workers, zero falha
inesperada, zero tarefa órfã e memória dentro do limite. Execuções curtas são
marcadas como desenvolvimento e não substituem essa evidência.
