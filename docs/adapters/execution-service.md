# Serviço de execução externo

`AgentExecutionService` é a fronteira única entre transportes externos e o
runtime. Ele traduz DTOs, resolve o agente, mapeia identidade, autoriza a
operação, aplica limites e converte o resultado para um formato estável.

## Registro e identidade

`AgentRegistry` é local à instância, mantém ordem de registro e rejeita IDs
duplicados. `ExecutionIdentityMapper` recebe somente `TransportPrincipal`,
produzido por autenticação confiável do host. O mapper padrão transfere apenas
`subject` e `tenant`; claims genéricas não viram roles ou permissões.

O body externo não aceita `user_id`, roles ou outros campos de autoridade.
`AgentAccessPolicy` é obrigatório e recebe agente, identidade e operação
(`execute` ou `resume`) antes do runtime.

## Limites e budget

`BoundedExecutionPolicyResolver` combina pedidos do cliente com tetos definidos
pelo servidor. Cada limite efetivo é o menor valor aplicável. A moeda do budget
é controlada pelo servidor; uma moeda divergente não amplia o custo permitido.
Essas políticas limitam consumo, mas não substituem rate limiting por origem.

## Idempotência

Operações não streaming aceitam uma chave opcional. O fingerprint SHA-256 usa o
conteúdo canônico da requisição e o escopo seguro de `subject` e `tenant`, mas
exclui claims e a própria chave. Reutilizar a chave com conteúdo ou identidade
diferente produz conflito.

`InMemoryIdempotencyStore` serve somente para testes e desenvolvimento. Seu
estado não sobrevive a reinício e não é compartilhado entre processos. Em
produção, implemente `IdempotencyStore` com reserva atômica, TTL, isolamento por
tenant e proteção adequada dos resultados. A abstração reduz reexecuções, mas
não promete exactly-once nem substitui transação/outbox.

## Retomada

O token é um bearer secret opaco e deve permanecer no payload protegido. O
serviço autoriza `resume` para o agente declarado; o `CheckpointStore` do core
continua responsável por consumo atômico, uso único e validação do checkpoint.
Em uma implantação distribuída, o host deve manter autorização consistente
entre o agente, a identidade atual e o checkpoint original.

## Readiness

`readiness()` verifica apenas a composição local e não chama providers. O
resultado fica pronto quando há ao menos um agente registrado. Verificações de
rede ou infraestrutura pertencem ao health system da aplicação hospedeira.
