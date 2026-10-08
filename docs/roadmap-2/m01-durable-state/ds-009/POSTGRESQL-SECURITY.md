# Segurança PostgreSQL

## Separação de papéis

| Capacidade | Runtime | Maintenance | Migration |
| --- | --- | --- | --- |
| USAGE no schema | sim | sim | sim |
| SELECT/INSERT/UPDATE/DELETE operacional | sim | somente tabelas necessárias | conforme necessidade |
| purge e auditoria | não por padrão | sim | não por padrão |
| CREATE/ALTER | não | não | sim |
| DROP schema | não | não | somente procedimento autorizado |

O teste real criou `atlas_ds009_runtime` com `USAGE` e DML, confirmou leitura e
confirmou `InsufficientPrivilege` para `CREATE TABLE`. Operação normal não exige
superuser. O papel de migration é provisionado externamente e não é derivado de
metadata ou payload.

As migrations não contêm segredo, DSN, shell ou SQL dinâmico. O checker consulta
somente catálogos e histórico; erros públicos não incluem query, credencial,
payload ou resume token. Arquivos SQL são recursos versionados do wheel e seus
checksums são verificados antes de confiar no histórico.

Grants sugeridos devem ser aplicados pela plataforma à identidade concreta; o
SDK não cria usuários ou concede privilégios em produção.
