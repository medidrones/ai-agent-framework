# Segurança do token de retomada

`ResumeToken.create()` usa `secrets.token_urlsafe(32)`. O boundary DS-014 guarda
apenas `HMAC-SHA-256(chave_do_host, token)` e compara em tempo constante. A chave
é injetada por configuração/Secret do host e nunca lida pelo core.

O token bruto:

- é devolvido uma única vez no corpo da suspensão técnica;
- é enviado somente no corpo JSON da decisão;
- não é aceito em URL;
- não aparece em resposta de auditoria, status, métricas ou eventos;
- não aparece nos logs Kubernetes verificados;
- não é serializado na tabela `hitl_approvals`.

Replay encontra o tombstone/consumo do backend e não reativa o checkpoint.
