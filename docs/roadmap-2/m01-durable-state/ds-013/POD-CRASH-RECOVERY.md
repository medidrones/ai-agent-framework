# Crash e restart de pods

Os testes encerraram pods abruptamente para PostgreSQL e Redis, substituíram o
worker por outra identidade e retomaram somente após decisão HITL. Cada efeito
aprovado terminou com contador `1`; a rejeição terminou com `0`.

Uma fault injection adicional matou o PID 1 imediatamente depois do efeito
externo fake e antes da confirmação do checkpoint. O contêiner reiniciou, o
lease foi reconciliado e o efeito idempotente permaneceu com contador `1`.
