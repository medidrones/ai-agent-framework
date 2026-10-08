# ADR-006 — Coordenação de recuperação de execuções

## Status

Aceita em 2026-10-08.

## Contexto

O contrato certificado de checkpoint do Atlas 1.x representa suspensões HITL.
`AgentRuntime.resume()` exige um `ResumeToken` e uma `ApprovalDecision` reais.
Não existe um ponto seguro e genérico para reconstruir uma execução arbitrária
interrompida fora desse estado.

## Decisão

O core recebe contratos provider-neutral e um
`ExecutionRecoveryCoordinator` acionado explicitamente pelo host. O coordinator
descobre metadados, valida elegibilidade, adquire lease, registra a tentativa,
carrega e restaura o checkpoint, revalida o estado e chama um
`ExecutionRecoveryInvoker`.

O primeiro invoker oficial cobre somente HITL autorizado. A decisão é obtida
por um `RecoveryResumeRequestResolver` injetado e nunca é inferida do
checkpoint. `AgentRuntime.resume()` e `resume_stream()` recebem o parâmetro
opcional e retrocompatível `lease`; quando presente, o store deve suportar
consumo autorizado e fenced na mesma transação.

O PostgreSQL implementa descoberta e auditoria durável em adapters opcionais.
O core não conhece SQL, pool, driver, scheduler ou ambiente de hospedagem.

## Consequências

- checkpoints HITL sem decisão permanecem suspensos;
- não há recuperação automática de estados sem API pública segura;
- ownership, autorização e consumo são verificados antes do efeito;
- tentativas e limites sobrevivem a restart;
- a conclusão `RECOVERED` significa continuidade confirmada pelo runtime, não
  exactly-once de efeitos em sistemas externos;
- scheduler, backoff temporal e retenção permanecem responsabilidade do host e
  das tarefas futuras.
