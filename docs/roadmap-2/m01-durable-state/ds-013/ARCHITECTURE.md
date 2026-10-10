# Arquitetura da DS-013

A baseline é o commit `2b47559c90df8423d7f5fb3c68f1ee08b2980529`,
Atlas `1.0.1`. O host técnico usa somente APIs públicas do Atlas.

```text
runner autorizado -> Service -> 2+ workers non-root
                              |-> PostgreSQLCheckpointStore + lease/fencing
                              |-> RedisCheckpointStore + consumo atômico
                              |-> volume privado de decisões HITL
                              `-> Redis como serviço fake de efeito idempotente
```

O core não recebeu dependências de infraestrutura. O exemplo injeta stores,
coordinator, fake provider e fake tool por construtor. O Kubernetes controla
disponibilidade; o Atlas controla checkpoint, ownership, fencing e autorização.

`ApprovedOnlyHITLRecoveryPolicy` compõe a política pública e impede que uma
passagem de discovery consuma o limite de tentativas antes de existir decisão
durável. Após a decisão, a validação autoritativa continua sendo feita pelo
`AuthorizedHITLRecoveryPolicy` sob lease.
