# Arquitetura da DS-014

## Direção das dependências

```text
Interface humana / IdP
        |
        v
Host confiável ──> DurableApprovalService ──> PostgreSQL (decisão + auditoria)
        |
        v
AgentRuntime ──> CheckpointStore ──> PostgreSQL ou Redis
        |
        v
Ferramenta idempotente / reconciliável
```

O core não conhece PostgreSQL, Redis, Kubernetes, identidade corporativa ou a
interface humana. O exemplo executável compõe esses elementos por injeção de
dependência. A ADR-010 formaliza o boundary.

## Fluxo

1. O runtime suspende antes da ferramenta e persiste o checkpoint.
2. O host registra o escopo e somente o HMAC do token.
3. Um host confiável fornece identidade, tenant, permissões e escopo de ferramenta.
4. O serviço valida token, escopo, autorização e expiração.
5. PostgreSQL lineariza a decisão e seu evento de auditoria.
6. O runtime consome atomicamente o checkpoint no backend escolhido.
7. O resultado da retomada é persistido para reconciliação.

Não existe alegação de exactly-once para efeitos externos.
