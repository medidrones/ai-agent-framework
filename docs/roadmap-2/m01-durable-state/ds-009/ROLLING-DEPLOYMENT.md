# Rolling deployment

A migration 007 é uma expansão: cria um índice e não remove, renomeia ou muda
coluna, constraint ou formato. O teste de compatibilidade aplicou 001–006,
gravou um checkpoint com o contrato anterior, aplicou 007 e confirmou sua
leitura pelas mesmas queries da revisão 6.

Sequência autorizada:

1. congelar migrations 001–006;
2. executar o migrator 007 com identidade administrativa;
3. confirmar `SCHEMA_COMPATIBLE` nos novos workers;
4. subir workers novos;
5. retirar workers antigos após health/readiness.

Workers da revisão 6 ignoram o índice adicional, portanto podem coexistir com
workers da revisão 7. Checkpoint, lease, fencing, consumo e purge não mudaram.
O `CREATE INDEX` comum pode aguardar locks e consumir I/O; por isso este teste
certifica compatibilidade funcional adjacente, mas não declara zero downtime
universal nem ausência de impacto em bancos de produção de qualquer tamanho.

Não existe fase contract nesta revisão. Uma futura mudança destrutiva exigirá
ADR, telemetria de adoção e release posterior à retirada do reader antigo.
