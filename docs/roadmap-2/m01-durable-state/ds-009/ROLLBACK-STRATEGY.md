# Estratégia de rollback e recuperação

Todas as revisões atuais usam DDL transacional do PostgreSQL. O advisory lock,
o DDL e o `INSERT` no histórico pertencem à mesma transação do context manager.

| Falha | Resultado esperado | Evidência |
| --- | --- | --- |
| antes do commit | DDL e histórico ausentes | migration sintética 008 falha após `CREATE TABLE`; ambos revertidos |
| cancelamento aguardando lock | task cancelada, conexão devolvida | runner subsequente aplica 001–007 |
| dois runners | uma aplicação efetiva | resultados 7 revisões e 0 revisões |
| queda após commit/ack incerto | rerun consulta histórico/checksum e retorna idempotente | repetição sem alteração |
| checksum divergente | bloqueio | checker e migrator rejeitam |
| versão desconhecida/lacuna | bloqueio | erro controlado |
| banco indisponível | erro seguro | DSN não exposta |

Não há DDL não transacional na linha atual, portanto reconciliação parcial não
se aplica. Não existe downgrade automático: rollback de aplicação mantém schema
aditivo; rollback destrutivo exige runbook, backup e autorização externa.

Deadlock/timeout seguem o rollback transacional do driver e são encapsulados em
`PostgreSQLMigrationError`. Um retry só é permitido após verificar o histórico.
