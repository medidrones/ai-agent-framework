# Segurança sob carga

O throughput nunca prevalece sobre integridade. A certificação exige todos os
contadores abaixo em zero:

```text
DUPLICATE_CONSUMPTIONS      = 0
UNAUTHORIZED_TOOL_CALLS     = 0
STALE_OWNER_WRITES          = 0
LOST_UPDATES                = 0
UNAUTHORIZED_PURGES         = 0
CROSS_TENANT_VIOLATIONS     = 0
UNSAFE_SIDE_EFFECT_RETRIES  = 0
SECRET_LEAKS                = 0
```

As disputas verificam consumo único, revisão condicional e ownership exclusivo.
O probe de stale owner exige rejeição após nova geração de fencing. Tenant e
identidade permanecem no checkpoint sintético; os testes de integração das
DS-012 a DS-014 exercitam autorização, recovery e HITL com os mesmos contratos.

Os relatórios não contêm DSN com senha, tokens de retomada, credenciais, prompts
reais ou dados pessoais. O Redis utiliza namespace efêmero e o PostgreSQL exige
banco explicitamente identificado como teste.
