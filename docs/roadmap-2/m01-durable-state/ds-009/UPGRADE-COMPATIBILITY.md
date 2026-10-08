# Compatibilidade de upgrade

## Fresh install

Em PostgreSQL 16 vazio, o runner aplicou 001–007, registrou sete checksums e a
segunda execução retornou conjunto vazio. O checker retornou
`SCHEMA_COMPATIBLE`.

## Instalação existente

O caminho 5→7 foi reproduzido com checkpoint na revisão 7 de storage e lease na
geração 11. Após 006/007, dados e gerações permaneceram `(7, false, 11)`. O
caminho adjacente 6→7 preservou checkpoint criado antes da expansão.

| Componente | Atual | Anterior testado | Estado |
| --- | ---: | ---: | --- |
| Checkpoint Store | 7 | 5 e 6 | `SUPPORTED` após migration |
| Lease Manager | 7 | 5 e 6 | `SUPPORTED` após migration |
| Recovery Coordinator | 7 | 6 | `SUPPORTED` após migration |
| Retention Policies | 7 | 5 e 6 | `SUPPORTED` após migration |
| Purge Coordinator | 7 | 6 | `SUPPORTED` após migration |
| Tombstones | 7 | 5 e 6 | `SUPPORTED` após migration |

As regressões PostgreSQL DS-002–DS-008 validam serialização, CAS, consumo,
lease, recovery, retenção e purge já no schema 7. Revisões 1–4 possuem caminho
de migration determinístico, mas não receberam fixtures históricos completos;
essa compatibilidade de dados permanece `NOT_VERIFIED`, sem impedir os caminhos
5/6 formalmente suportados nesta certificação.
