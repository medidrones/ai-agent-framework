# Fencing tokens

Cada aquisição bem-sucedida de uma linha já existente incrementa
`fencing_token`. Expiração e release não removem nem reiniciam a geração.

`compare_and_swap_leased()` combina revisão DS-003, identidade do checkpoint,
owner, token e expiração em um único `UPDATE`. `consume_authorized_leased()`
combina lease e consumo DS-004 em um único `DELETE ... RETURNING`. Assim, a
validação não é separada da mutação e não existe janela TOCTOU.

O token é um contador de ordenação, não um segredo. Sistemas externos somente
ficam protegidos se também aceitarem fencing ou idempotência. O Atlas não
declara exactly-once para efeitos externos.
