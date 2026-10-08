# Integração de fencing

O lease Redis é token-scoped e reside no mesmo hash do checkpoint. Aquisição
emite geração monotônica; renovação e liberação exigem owner, execution ID,
geração e validade. O token de fencing nunca retrocede após release ou expiração.

`compare_and_swap_leased` e `consume_authorized_leased` verificam o lease no
mesmo script que realiza a mutação. O teste de troca de owner comprovou que a
geração anterior é rejeitada e a nova geração é aceita.

Leases PostgreSQL não protegem atomicamente checkpoints Redis. Essa composição
não é anunciada; tentar exigir lease em runtime sem a capability correspondente
continua falhando de forma fechada.
