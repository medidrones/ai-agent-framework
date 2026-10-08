# Retomada HITL

Autorização permanece no validador confiável do runtime. O adapter lê uma
revisão, o callback síncrono valida a decisão e o script consome exatamente essa
revisão e digest. Rejeição ou identidade inválida não inicia o consumo.

Evidências reais:

- pending: nenhuma ferramenta executada;
- rejected: checkpoint consumido uma vez e nenhuma ferramenta executada;
- approved: retomada única após restart do runtime;
- 100 resumes aprovados simultâneos: uma continuação e uma tool call.

O teste não afirma exactly-once sob falha de efeitos externos.
