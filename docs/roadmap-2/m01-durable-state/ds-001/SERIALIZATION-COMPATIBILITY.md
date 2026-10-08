# Serialização e compatibilidade

## Formato certificado

`ExecutionCheckpoint` é um modelo Pydantic congelado, com `extra="forbid"`.
`model_dump_json()` e `model_validate_json()` oferecem round-trip determinístico
para o schema v1. A fixture
`tests/fixtures/checkpoints/execution-checkpoint-v1.json` fixa uma amostra
compatível e carregável.

As validações rejeitam campos desconhecidos, versão não positiva, timestamps
sem timezone, metadata não JSON, journal inconsistente e ausência de chamada
pendente. A restauração aceita somente
`CURRENT_CHECKPOINT_VERSION`; não há migração ou upcaster.

## Política recomendada para adapters

- armazenar os bytes JSON sem mutação semântica;
- manter `checkpoint_version` separado de uma revisão física do registro;
- validar o modelo antes de gravar e depois de ler;
- proteger integridade em repouso e em trânsito;
- nunca serializar token dentro do payload;
- tratar adição/remoção de campos como evolução explícita de schema;
- preservar fixtures de cada versão suportada.

## Compatibilidade

| Caso | Estado |
| --- | --- |
| v1 produzido e consumido pela 1.0.1 | Certificado |
| Campo desconhecido | Rejeitado |
| Versão futura | Rejeitada explicitamente |
| Migração de versão antiga | Não implementada |
| Codec canônico independente de Pydantic | Não definido |
| Compatibilidade binária entre codecs externos | Fora do contrato |

Lacuna associada: `DS001-GAP-008`.
