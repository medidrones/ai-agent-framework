# Falhas sob carga

O modo `--fault-probe-seconds` executa ciclos concorrentes de save, read e
consume durante uma indisponibilidade real do backend. O processo externo de
certificação reinicia somente o container isolado selecionado.

O probe somente passa quando comprova simultaneamente:

- pelo menos uma falha de infraestrutura observada;
- nenhuma confirmação falsa;
- operações concluídas antes da falha;
- operações concluídas depois da recuperação;
- retorno do backend sem alteração de contrato.

Timeout, cancellation e stale lease são validados separadamente no runner. Os
cenários de crash de worker, restart de pod, rolling deployment, fencing,
recovery e HITL reutilizam as certificações reais DS-012, DS-013 e DS-014.

Falhas controladas não são misturadas ao error rate do benchmark normal. Os
resultados brutos ficam em `results/fault-postgresql.json` e
`results/fault-redis.json`.
