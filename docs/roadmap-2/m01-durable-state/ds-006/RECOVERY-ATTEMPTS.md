# Tentativas de recovery

A migration 004 cria `atlas_agent.execution_recovery_attempts` com UUID,
execução, digest opaco do checkpoint, owner, fencing, número, timestamps,
outcome e reason code. Não há token, payload ou credencial.

A admissão calcula atomicamente o próximo número e verifica lease e limite. A
restrição única impede duplicação do mesmo número. Uma tentativa incompleta
permanece auditável após crash e conta para o limite; um processo posterior
pode reavaliar e usar a próxima tentativa disponível.

Não há retry infinito ou backoff interno. O host decide quando chamar um novo
lote. DS-007/DS-008 poderão definir retenção desses registros sem alterar a
semântica desta tarefa.
