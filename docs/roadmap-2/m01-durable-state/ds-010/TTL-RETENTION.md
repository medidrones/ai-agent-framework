# TTL, expiração e retenção

Três prazos permanecem distintos:

```text
expiração lógica != TTL físico Redis != prazo de retenção
```

O menor prazo entre aprovação e política HITL define a expiração lógica. O Lua
usa o relógio Redis e considera expirado quando `now >= expires_at`. O TTL
nativo aponta para `expires_at + expired_retention`; portanto, não remove a
chave antes da janela de auditoria. Após consumo, um novo prazo é calculado com
`consumed_retention` e o payload é removido imediatamente.

Sem política explícita, a compatibilidade 1.x usa retenção de tombstone de 30
dias. Legal hold e purge administrativo Redis não pertencem à DS-010.
