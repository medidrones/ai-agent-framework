# Lease e fencing

As tentativas PostgreSQL registraram owner por nome do pod e fencing token. A
aquisição concorrente resultou em um único recovery; stale owners são rejeitados
pelos contratos certificados nas DS-005, DS-006 e pela regressão real desta
tarefa.

A fault injection após side effect comprovou recuperação depois da perda do
processo. O benchmark de expiração/reconciliação mediu 3.396,652 ms com lease de
5 segundos configurado; a observação inclui discovery e scheduling local.
