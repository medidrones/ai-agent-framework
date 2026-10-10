# Graceful shutdown

O Deployment usa `terminationGracePeriodSeconds: 20` e hook `preStop`. O host
para de anunciar readiness, encerra o servidor e libera recursos. O audit log
persistido confirmou `atlas.worker.shutdown`; o replacement ficou ready em
aproximadamente 6 segundos e recuperou o checkpoint pendente.

Se o prazo for excedido, a segurança depende do checkpoint confirmado, lease e
fencing. O processo não estende deadlines absolutos; deadline e cancellation
foram exercitados dentro do pod e terminaram em `timed_out` e `cancelled`.
