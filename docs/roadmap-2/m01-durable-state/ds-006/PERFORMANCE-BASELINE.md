# Baseline de performance

Ambiente local: Windows, Python 3.13.15, PostgreSQL 16 Alpine em Docker, TCP
local, pool assíncrono e 30 amostras por operação.

| Operação | Mediana | p95 | Amostras |
| --- | ---: | ---: | ---: |
| descoberta limitada | 1,325 ms | 1,992 ms | 30 |
| aquisição de lease | 1,820 ms | 2,594 ms | 30 |
| recovery completo | 12,561 ms | 14,680 ms | 30 |

As 30 recuperações foram concluídas com taxa de sucesso de 100%, zero conflito
e zero falha no cenário sem contenção. O throughput derivado da mediana do
recovery foi aproximadamente 79,6 tentativas/s. Os valores são referência
local, não SLO; rede, contenção, fsync e configuração alteram o resultado.
