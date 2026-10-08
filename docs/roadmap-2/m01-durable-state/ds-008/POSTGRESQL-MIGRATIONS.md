# Migration PostgreSQL da DS-008

A migration imutável `006_create_checkpoint_purge.sql`:

- conecta o `legal_hold` já existente no contrato DS-007 às tabelas duráveis;
- adiciona índices parciais/ordenados de candidatos;
- cria auditoria transacional com constraints de tipo e outcome;
- não cria `CASCADE`, trigger destrutivo ou migration automática.

O migrator mantém checksum, versão sequencial e advisory lock. O rollback
operacional exige parar workers, preservar/exportar auditoria e então remover
índices, tabela e colunas de forma deliberada; downgrade automático destrutivo
não é oferecido. PostgreSQL 16 foi certificado; o SQL usa recursos suportados
pela matriz atual do adapter.
