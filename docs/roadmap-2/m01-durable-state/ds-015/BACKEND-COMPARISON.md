# Comparação PostgreSQL × Redis

| Dimensão | PostgreSQL | Redis |
| --- | --- | --- |
| persistência | transações/WAL | AOF `always` standalone |
| consumo | `DELETE ... RETURNING` | script Lua atômico |
| optimistic concurrency | revisão condicional SQL | revisão condicional Lua |
| leases | tabela e relógio PostgreSQL | lease no envelope e relógio Redis |
| recovery discovery | repository SQL certificado | composição, sem repository isolado equivalente |
| retention/purge | repositories e auditoria | TTL/retention do adapter |
| falha testada | restart do container | restart com AOF |

As medições usam o mesmo host, payloads, amostras e níveis de concorrência. Os
soaks podem se sobrepor e compartilhar CPU; por isso os números validam cada
backend contra thresholds próprios, mas não fundamentam ranking direto. Eles
também não tornam equivalentes as garantias de durabilidade.

Nenhum backend é declarado universalmente superior. A seleção continua sendo
responsabilidade do host conforme consistência, recuperação, operação e custo.
