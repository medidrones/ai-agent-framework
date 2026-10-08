# Revisão de segurança

- token persistido somente como SHA-256 ou HMAC-SHA-256;
- tombstone sem payload e sem segredo;
- filtro de tenant aplicado no banco;
- parâmetros SQL vinculados, sem interpolação;
- política inválida e estado incompatível falham fechados;
- classificação não possui operação de escrita;
- lease/fencing e autorização transacional foram preservados.

O scan final e suas versões são registrados em `TEST-EVIDENCE.md`.
