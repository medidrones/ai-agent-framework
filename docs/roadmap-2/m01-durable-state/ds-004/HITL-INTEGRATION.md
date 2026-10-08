# Integração HITL

`AgentRuntime.resume()` e `resume_stream()` encaminham a decisão para a etapa de
consumo. Quando o store oferece `consume_authorized`, o runtime fornece um
callback síncrono que:

1. exige a mesma modalidade (`run` ou `stream`) do checkpoint;
2. valida o `approval_request_id`;
3. delega regras adicionais ao `ApprovalDecisionValidator` injetado.

Somente após o commit o runtime restaura `ExecutionState`, registra a retomada e
avalia a decisão. Uma rejeição válida produz resultado `REJECTED` sem ferramenta.
Uma aprovação válida libera a chamada pendente.

Validators customizados podem exigir `decided_by`, tenant, papel ou política
externa. A DS-004 prova que uma identidade recusada não consome o checkpoint e
não executa ferramenta.

Stores 1.x sem a capability permanecem funcionais: o runtime consome e valida
em seguida, preservando compatibilidade, mas sem a proteção transacional
adicional do adapter PostgreSQL.
