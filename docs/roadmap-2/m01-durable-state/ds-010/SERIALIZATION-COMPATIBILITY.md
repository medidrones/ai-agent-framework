# Compatibilidade de serialização

O payload é o JSON v1 oficial de `ExecutionCheckpoint`, gerado com
`model_dump(mode="json")`. A codificação usa chaves ordenadas e separadores
canônicos para produzir digest determinístico. Não há `pickle` nem objeto vivo.

O hash contém `schema_version=1`, separado de `checkpoint_version`. Envelope
desconhecido gera `UnsupportedCheckpointVersionError`; JSON inválido, modelo
incompatível ou identidade divergente gera `InvalidCheckpointError` antes de
qualquer resume.

PostgreSQL e Redis podem usar envelopes físicos diferentes, mas recuperam o
mesmo objeto semântico. A fixture certificada da baseline 1.0.1 foi validada.
