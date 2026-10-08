# Revisão de segurança

## Controles verificados

- SQL parametrizado e digest de token;
- tokens, DSN e payloads ausentes das mensagens de erro;
- token desconhecido, expirado e consumido indistinguíveis externamente;
- validator executado antes do commit;
- identidade customizada recusada sem consumo ou ferramenta;
- callback síncrono, sem I/O ou efeito externo na transação;
- payload validado antes da autorização;
- core sem dependência PostgreSQL.

## Modelo de autorização

O validator padrão exige correspondência exata do `approval_request_id`. Regras
de identidade não são presumidas pelo SDK: aplicações que exigem identidade,
tenant ou papel devem injetar `ApprovalDecisionValidator`. O simples
conhecimento de um checkpoint ID não concede retomada; a API usa o bearer token
opaco e a decisão correspondente.

## Riscos residuais

- vazamento do bearer token permite tentativa de consumo conforme a política do
  validator configurado;
- payloads exigem criptografia, backup e ACLs da plataforma;
- perda de conexão após commit pode produzir resultado ambíguo;
- efeitos externos posteriores exigem idempotência própria.
