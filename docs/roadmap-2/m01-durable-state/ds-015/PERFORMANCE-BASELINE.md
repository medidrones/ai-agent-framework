# Baseline de performance do Durable State

Esta baseline foi obtida no commit certificado de entrada
`92ffe70948e1755ce4a4f9ab95157dd731d824ee`, com Atlas `1.0.1`. Ela serve como
referência reprodutível para detectar regressões; não constitui SLO de produção.

| Indicador | PostgreSQL | Redis |
| --- | ---: | ---: |
| p95 a 50 workers | 190,681 ms | 79,715 ms |
| p95 a 100 workers | 196,733 ms | 123,864 ms |
| p95 a 250 workers | 487,491 ms | 285,026 ms |
| p95 a 500 workers | 909,109 ms | 533,686 ms |
| throughput a 250 workers | 465,256 ciclos/s | 726,488 ciclos/s |
| throughput a 500 workers | 492,837 ciclos/s | 769,313 ciclos/s |
| ciclos no soak de 60 min | 1.096.355 | 1.358.054 |
| p95 do soak | 197,121 ms | 176,724 ms |
| p99 do soak | 233,160 ms | 206,519 ms |
| crescimento de memória | 36.219.069 B | 44.696.594 B |
| tarefas órfãs | 0 | 0 |

## Interpretação

Redis apresentou menor latência e maior throughput neste host. PostgreSQL
permaneceu dentro dos limites inclusive no perfil extremo de 500 workers. Essa
comparação não altera as garantias: PostgreSQL continua sendo a referência para
durabilidade transacional; Redis permanece condicionado à configuração AOF,
à política de persistência e às limitações declaradas na DS-010/DS-011.

Uma futura execução somente poderá ser comparada diretamente se preservar
hardware, versões, configuração de persistência, payloads, amostras e níveis de
concorrência. Mudanças nessas variáveis exigem uma nova linha de baseline.
