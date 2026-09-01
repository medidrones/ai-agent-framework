# ADR-001 — Ownership da execução pelo AgentRuntime

## Contexto

O contrato histórico `Agent` expõe `run()` e `stream()`, enquanto a evolução do
core passou a exigir um componente único para coordenar lifecycle, estado,
seleção, provider, eventos e resultados. Implementar o loop em ambos criaria
dois comportamentos concorrentes e permitiria divergência de invariantes.

## Decisão

`AgentRuntime` é o único proprietário da orquestração de execução.

`AgentDefinition` permanece declarativo. `ExecutionState` continua responsável
somente pelo estado mutável controlado. `ModelProvider` realiza a interação com
o modelo, e `AgentResult` representa o resultado público terminal.

O contrato abstrato `Agent` é preservado por compatibilidade. Implementações de
`Agent.run()` deverão funcionar somente como fachadas que delegam ao runtime;
não poderão manter um segundo execution loop. `Agent.stream()` permanece sem
implementação no runtime até a introdução formal do pipeline de streaming.

## Consequências

- lifecycle, eventos, erros e chamadas de modelo possuem um único coordenador;
- adapters podem continuar oferecendo uma API orientada a `Agent`;
- testes do runtime cobrem o comportamento end-to-end uma única vez;
- o runtime recebe registry e demais dependências por injeção explícita;
- novas formas de execução deverão evoluir no runtime, sem duplicação em
  agentes concretos.

## Compatibilidade

Nenhuma assinatura existente de `Agent` foi removida. Código atual continua
podendo implementar o contrato abstrato, mas deve delegar sua execução ao
`AgentRuntime`. A mudança formaliza ownership sem quebrar a API pública.
