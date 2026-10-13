# Metodologia dos benchmarks

## Relógio e estatística

As latências usam `time.perf_counter()` e são preservadas em milissegundos sem
arredondamento destrutivo. Para cada operação são registrados mínimo, mediana,
p95, p99, máximo, quantidade de amostras e throughput. Os percentis usam
nearest-rank sobre amostras ordenadas.

Cada workload possui warmup separado. O preparo de um checkpoint não participa
da latência de read, compare-and-swap, consume ou lease. Em contenção, o
throughput considera todas as tentativas; a distribuição de latência do
vencedor não é confundida com o custo agregado da disputa.

## Fases

1. baseline isolada com 30 amostras por operação e payload;
2. concorrência com 1, 10, 50, 100, 250 e 500 workers;
3. contenção com 100 e 500 consumidores, writers e owners;
4. semânticas de timeout, cancelamento e stale owner;
5. soak de 3.600 segundos com 50 workers por backend;
6. benchmarks especializados de recovery, retention/purge, HITL e Kubernetes;
7. quality gates e instalação limpa.

## Ambiente

Os resultados finais registram Python, Atlas, sistema operacional, CPU lógica,
versões e configurações do backend. PostgreSQL e Redis são executados em
containers separados ligados somente ao loopback. Redis usa AOF,
`appendfsync always` e `noeviction`.

## Comparabilidade

Os backends usam processos e containers separados no mesmo host. Os soaks
podem se sobrepor e, por isso, os valores não são usados para um ranking direto.
As garantias de persistência também não são equivalentes. A comparação é
informativa e não seleciona um backend universal.

Não existe baseline histórica consolidada com a mesma matriz, hardware,
instrumentação e duração. Esta execução estabelece a baseline inicial:

```text
PERFORMANCE_BASELINE = ESTABLISHED
REGRESSION_COMPARISON = NOT_AVAILABLE
```

## Repetição

O entry point é `atlas-durable-state-performance-certify`. A execução exige
backend, endpoint explícito, destino JSON e a flag
`--confirm-test-environment`. O soak padrão é de 3.600 segundos; reduzi-lo cria
apenas evidência de desenvolvimento e não satisfaz o gate DS015-G19.
