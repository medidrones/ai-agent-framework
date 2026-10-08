# Revisão de segurança

- resume tokens continuam armazenados somente como digest;
- credenciais/DSN não são incluídos nas exceções públicas;
- todas as queries usam parâmetros;
- owner metadata não concede autorização;
- lease não ignora revisão otimista nem autorização HITL;
- checkpoints consumidos não podem ser reativados;
- não há estado global, leitura de segredos ou acesso de rede no core;
- stale owner/token é rejeitado na mesma instrução da mutação protegida.

O payload persistido pode conter dados sensíveis; criptografia, backups e
permissões do banco continuam sob responsabilidade da plataforma operadora.
