# Detecção de schema drift

`PostgreSQLSchemaCompatibilityChecker.check()` é uma operação assíncrona,
somente leitura e com resultado Pydantic imutável.

| Status | Significado |
| --- | --- |
| `SCHEMA_COMPATIBLE` | revisão 7, checksums e catálogo compatíveis |
| `SCHEMA_DRIFT_DETECTED` | checksum, coluna, tipo, nulabilidade, constraint ou índice divergiu |
| `SCHEMA_VERSION_UNSUPPORTED` | migration pendente, versão desconhecida ou lacuna |
| `SCHEMA_NOT_INITIALIZED` | tabela de histórico inexistente |

O resultado inclui versão atual, alvo e issues seguras (`code`, `object_name`,
`detail`). O checker não lê JSONB, tokens ou credenciais, não aplica migrations
e não tenta corrigir o banco. Indisponibilidade gera
`PostgreSQLSchemaCheckError` sem expor DSN.

Foram testados: banco vazio, revisão 5, revisão desconhecida 99, checksum
adulterado, índice removido e coluna obrigatória removida.
