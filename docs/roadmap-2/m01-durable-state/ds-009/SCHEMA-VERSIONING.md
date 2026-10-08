# Versionamento do schema

Quatro versões independentes são preservadas:

| Versão | Responsabilidade |
| --- | --- |
| pacote Python | compatibilidade da distribuição Atlas 1.x |
| `checkpoint_version` | formato serializado do checkpoint |
| `revision` | compare-and-swap de uma linha |
| migration version | forma relacional do componente PostgreSQL |

A revisão relacional atual é 7; isso não altera `checkpoint_version = 1` nem a
versão pública `1.0.1`. A compatibilidade certificada é:

| Schema | Estado para este adapter | Ação |
| --- | --- | --- |
| 7 | `SUPPORTED` | operar |
| 6 | `MIGRATION_REQUIRED` | aplicar 007; coexistência adjacente testada |
| 5 | `MIGRATION_REQUIRED` | aplicar 006 e 007; preservação testada |
| 1–4 | `MIGRATION_REQUIRED`, histórico válido | caminho sintático suportado; dados históricos específicos não recertificados nesta tarefa |
| 0/sem histórico | `SCHEMA_NOT_INITIALIZED` ou unsupported | inicializar explicitamente |
| >7, lacuna ou revisão desconhecida | `UNSUPPORTED` | bloquear |

Mudanças aditivas, colunas nullable e índices são permitidos somente após teste.
Remoção silenciosa, tipo incompatível, regressão de fencing e quebra do payload
são proibidos na linha 1.x.
