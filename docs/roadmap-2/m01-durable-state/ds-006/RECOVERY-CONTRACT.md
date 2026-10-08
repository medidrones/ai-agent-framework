# Contrato de recovery

`RecoveryPolicy` limita lote, tentativas, lease, timeout e tenant. Candidatos
contêm somente identidade e metadados; resume tokens e payloads não aparecem na
descoberta.

`RecoveryBatchResult` classifica cada candidato exatamente uma vez como
`RECOVERED`, `STARTED`, `SKIPPED`, `CONFLICT`, `FAILED` ou `BLOCKED`. Os
contadores são validados contra os resultados individuais.

`RECOVERED` indica retorno terminal confirmado pela API pública. `STARTED`
indica continuidade aceita que voltou a suspender. `BLOCKED` é uma condição
segura que exige ação externa ou suporte adicional. O contrato não afirma
exactly-once para efeitos externos.

O coordinator é async, não mantém estado global e não inicia tarefas em
background. Retries temporizados e frequência de execução pertencem ao host.
