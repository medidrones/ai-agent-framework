# Preservação de tombstones

Ao remover um checkpoint, a mesma transação grava um tombstone sem payload com
digest opaco, execução, agente, tenant, instante, prazo, versão da política e a
maior geração de fencing conhecida. O prazo mínimo novo é a janela
`consumed_retention`; um tombstone existente nunca é encurtado.

O `CheckpointStore.save()` continua rejeitando o digest protegido. Tombstones
só entram como candidatos após `retention_until`; depois dessa eliminação a API
não promete proteção indefinida contra replay. Auditoria histórica permanece.
