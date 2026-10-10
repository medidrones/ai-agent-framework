# Recovery HITL

Resume tokens ficam somente no volume privado, com arquivos `0600`; nunca são
registrados em log ou checkpoint público. Pending sobreviveu a pod restart,
rolling update e scale. Aprovação válida realizou um consumo; rejeição concluiu
sem executar a tool; nova decisão sobre checkpoint consumido não repetiu efeito.

O coordinator filtra `tenant-ds013`. Um checkpoint aprovado de `tenant-other`
permaneceu sem tentativa, comprovando ausência de cross-tenant recovery.
