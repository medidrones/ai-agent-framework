# Reconciliação de efeitos externos

`ExternalEffectStatus` representa somente evidência comprovada:
`NOT_EXECUTED`, `EXECUTED` ou `UNKNOWN`. Resultado desconhecido produz
`RECONCILIATION_REQUIRED`; efeito executado só permite continuidade após
`reconciliation_verified`.

Uma idempotency key não é, isoladamente, prova de exactly-once. Retry só é seguro
quando o serviço externo declara e preserva a semântica correspondente. Ferramenta
não idempotente sem consulta externa permanece bloqueada para intervenção.

O journal `ToolCallRecord` preserva somente resultados concluídos. A DS-012 não
amplia esse journal nem promete exactly-once para sistemas externos.

