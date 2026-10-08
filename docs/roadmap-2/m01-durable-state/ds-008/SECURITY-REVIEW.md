# Revisão de segurança

- autorização destrutiva explícita; autenticação permanece no host;
- escopo de tenant é derivado da autorização e reaplicado na consulta;
- SQL parametrizado e identificadores de tabela compostos somente em teste;
- payloads e tokens não são carregados pela descoberta nem auditados;
- legal hold, lease, recovery, schema e política operam fail-closed;
- usuário de runtime, manutenção e migrations deve usar menor privilégio;
- nenhuma rede, segredo ou driver PostgreSQL foi adicionado ao core;
- nenhuma migration ou execução ocorre implicitamente.

O purge não interpreta metadata de mensagens, owner do checkpoint ou headers
como prova de autorização.
