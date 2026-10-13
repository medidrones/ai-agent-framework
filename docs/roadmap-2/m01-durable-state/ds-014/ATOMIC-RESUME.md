# Retomada atômica

PostgreSQL usa `DELETE ... RETURNING` e tombstone; Redis usa script Lua com
tombstone. Esses pontos de linearização permanecem os responsáveis pelo consumo
único. O registro da decisão ocorre antes da retomada e pode ser repetido com o
mesmo `decision_id` depois de crash.

No teste Kubernetes com 100 tentativas concorrentes houve:

```text
completed         1
already_consumed 99
```

O resultado prova at-most-once para a autorização de retomada, não exactly-once
para efeitos externos.
