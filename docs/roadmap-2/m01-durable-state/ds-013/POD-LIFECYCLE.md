# Lifecycle de pods

O worker inicializa migrations, pool PostgreSQL, cliente Redis e diretório
privado antes de ficar ready. Readiness depende dos backends; liveness verifica
apenas o processo local, evitando restart loop durante falha transitória de
persistência.

SIGTERM fecha o servidor, cancela o loop de recovery e libera pool e cliente.
Eventos `atlas.worker.started` e `atlas.worker.shutdown` são registrados sem
tokens ou credenciais. Pod kill, replacement e reinício do contêiner no mesmo
UID de pod foram executados com recovery posterior.
