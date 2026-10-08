# Tombstones de replay

O consumo atômico remove o checkpoint e insere um tombstone na mesma transação.
Ele contém digest do token, identidades mínimas, tenant, instante, prazo,
versão da política e fencing opcional. Não contém token em claro, payload,
decisão, credencial ou conteúdo recuperado. O digest único impede reuso durante
a janela de retenção.
