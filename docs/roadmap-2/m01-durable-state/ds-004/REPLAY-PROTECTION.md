# Proteção contra replay

## Token de retomada

O token é armazenado somente como HMAC-SHA-256 ou SHA-256. O primeiro consumo
autorizado remove a linha; qualquer nova tentativa recebe a mesma resposta
segura usada para token desconhecido ou expirado.

## Checkpoint

O payload não pode ser reativado silenciosamente. `save()` é create-only e
colisões falham; `compare_and_swap()` exige linha ativa e revisão vigente.

## Decisões inválidas

Uma decisão com request incompatível, modalidade incorreta ou identidade
recusada não é tratada como replay: a transação sofre rollback para permitir
uma decisão legítima posterior. Uma decisão `REJECT` válida é terminal e
consome o token.

## Limite da garantia

A proteção cobre autorização e estado persistido. Idempotência de ferramentas,
outbox e reconciliação de efeitos externos pertencem a protocolos posteriores.
