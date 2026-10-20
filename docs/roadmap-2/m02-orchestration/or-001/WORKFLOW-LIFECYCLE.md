# Lifecycle de workflow

Os estados públicos são `created`, `ready`, `running`, `waiting`, `succeeded`,
`failed`, `cancelled` e `timed_out`.

- iniciais: `created` e, após preparação futura, `ready`;
- ativos: `running`;
- espera, inclusive futuro HITL: `waiting`;
- terminais: `succeeded`, `failed`, `cancelled` e `timed_out`.

Cancelamento indica encerramento solicitado; timeout indica deadline excedido.
A OR-001 fornece terminalidade e consistência de resultados, mas não uma
máquina operacional nem validação completa de transições.
