# ADR-010 — Autorização HITL durável no host

## Status

Aceita em 2026-10-13.

## Contexto

O core do Atlas já define solicitações, decisões, suspensões e tokens opacos. A
DS-014 precisa certificar identidade, autorização, durabilidade e auditoria sem
acoplar o core a banco, autenticação ou interface humana.

## Decisão

A aplicação hospedeira autentica a pessoa e injeta uma identidade confiável. Um
boundary opcional persiste no PostgreSQL o escopo da aprovação, o HMAC do token,
a decisão e a auditoria. O token bruto permanece somente com seu portador e no
corpo da requisição de retomada; não é persistido pelo boundary, registrado ou
incluído em URL. O checkpoint continua no adapter PostgreSQL ou Redis existente.

A decisão é vinculada a `tenant_id`, `execution_id`, `approval_request_id`,
`tool_call_id` e `tool_name`. A persistência da decisão e de seu evento de
auditoria ocorre na mesma transação. A retomada usa o consumo atômico já
certificado pelo backend e registra depois um resultado reconciliável.

## Consequências

- o core e seus contratos 1.x permanecem inalterados;
- a autenticação continua responsabilidade do host;
- uma decisão confirmada sobrevive a falha antes da retomada e pode ser repetida
  com o mesmo `decision_id`;
- decisões conflitantes falham fechadas;
- não há transação distribuída entre a decisão e efeitos externos;
- exactly-once universal continua explicitamente fora da garantia.
