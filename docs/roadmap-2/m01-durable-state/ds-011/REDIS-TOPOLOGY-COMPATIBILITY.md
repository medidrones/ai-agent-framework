# Compatibilidade de topologia Redis

| Topologia | Estado | Evidência |
| --- | --- | --- |
| Standalone 7.4.11 | Suportada | integração, restart, concorrência e benchmark |
| Sentinel | Não anunciada | failover real não executado |
| Cluster | Não anunciada | cluster real não executado |

As operações são single-key. A chave usa
`atlas:{namespace_digest:token_digest}:checkpoint`, mantendo todas as estruturas
do checkpoint no mesmo slot e distribuindo checkpoints entre hash slots. Essa
propriedade evita `CROSSSLOT` por construção, mas não equivale à certificação de
Cluster, que exige testes reais de MOVED/ASK, resharding e falha.
