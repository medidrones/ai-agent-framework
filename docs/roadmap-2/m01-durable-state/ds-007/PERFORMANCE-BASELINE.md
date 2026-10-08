# Baseline de performance

A validação mediu a classificação de 30 checkpoints em PostgreSQL 16 Alpine,
Docker local no Windows, Python 3.13.15. Foram realizadas 30 amostras após a
carga dos registros:

| Operação | Mediana | p95 | Amostras |
| --- | ---: | ---: | ---: |
| Classificação limitada a 100 registros | 1,227 ms | 2,546 ms | 30 |

A consulta usa índices de `retention_until`, tenant e execução, é limitada e
ordenada e não carrega payload. O gate conservador de p95 inferior a 500 ms
passou. O resultado é baseline local, não SLO de produção.
