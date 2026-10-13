# Revisão de segurança

## Controles verificados

- HMAC-SHA-256 com chave mínima de 32 bytes;
- comparação em tempo constante;
- token fora de URL, logs, auditoria e banco de aprovação;
- autorização por tenant, permissão e ferramenta;
- binding completo da decisão;
- SQL parametrizado;
- payload JSON limitado a 16 KiB;
- IDs externos validados;
- erros HTTP tipados sem dados de infraestrutura;
- isolamento por NetworkPolicy e execução non-root;
- rollback da decisão se a auditoria falhar.

## Limites

O exemplo recebe uma identidade já autenticada; não implementa autenticação,
SSO ou UI. TLS, criptografia de volume, backup e least privilege de produção
pertencem à plataforma hospedeira.
