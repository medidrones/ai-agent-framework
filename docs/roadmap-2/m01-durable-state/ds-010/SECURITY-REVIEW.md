# Revisão de segurança

- nenhuma senha, URL ou token hardcoded no adapter;
- nenhuma leitura automática de `REDIS_URL`;
- namespace e token convertidos em digests; HMAC opcional;
- erros públicos sanitizados;
- JSON/Pydantic em vez de pickle;
- scripts Lua estáticos, nunca originados de input;
- nenhuma operação administrativa ou busca global no adapter;
- payload removido no consumo e tombstone preservado;
- autorização inválida não consome nem executa ferramenta;
- isolamento do core confirmado pela dependência opcional.

TLS (`rediss://`), ACL mínima e rotação de credenciais pertencem ao deployment.
O host não deve incluir segredos no namespace e deve proteger a chave HMAC.
