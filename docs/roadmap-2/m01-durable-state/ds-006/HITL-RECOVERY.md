# Recovery e HITL

O checkpoint não é uma autorização. `RecoveryResumeRequestResolver` representa
uma fonte segura controlada pelo host e fornece em memória o `ResumeToken` e a
`ApprovalDecision` reais. Nenhum desses valores é persistido na tabela de
tentativas ou retornado pela descoberta.

Sem decisão, a execução permanece `WAITING_FOR_APPROVAL`. Rejeições não
executam ferramentas. Aprovações seguem o mesmo validator, identidade,
permissões, limites, budget e pipeline de ferramentas de `AgentRuntime`.

O invoker oficial usa `resume()` para checkpoints run e `resume_stream()` para
checkpoints stream. Uma nova suspensão produz `STARTED`; um resultado terminal
produz `RECOVERED`.
