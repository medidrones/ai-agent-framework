# Análise de vazamento de recursos

O runner mede memória e tarefas antes e depois do soak. O lifecycle pertence ao
host: o pool PostgreSQL e o cliente Redis são injetados, permanecem abertos
durante a suíte e são fechados uma única vez no encerramento.

Os workloads liberam leases criados para medições isoladas e consomem os
checkpoints temporários. O cenário de lease contention mantém somente o owner
vencedor até o fim da execução, como evidência intencional de exclusividade; o
namespace e o container são descartados depois da certificação.

Critérios:

- crescimento líquido de memória ≤ 64 MiB;
- zero tarefa assíncrona órfã;
- zero fechamento indevido de cliente/pool injetado;
- nenhuma falha de cleanup;
- containers removidos ao final da certificação.
