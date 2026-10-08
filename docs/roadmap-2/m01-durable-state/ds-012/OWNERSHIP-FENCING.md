# Ownership e fencing

O fluxo adquire lease antes de carregar o payload autoritativo, revalida o estado e
propaga o mesmo fencing token às operações protegidas. PostgreSQL e Redis rejeitam
owner obsoleto. Lease expirado permite nova geração, nunca continuidade pela geração
anterior.

Evidências incluem 2 coordinators, processos independentes, 20/100 consumidores,
lease expirado durante recovery e tentativa de conclusão com fencing obsoleto.
Todos produziram exatamente um vencedor ou bloqueio controlado.
