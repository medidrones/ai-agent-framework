# Prontidão para adapter Redis

## Mapeamento recomendado

O token deve ser transformado em chave não reversível; o valor deve conter o
JSON v1 protegido conforme o ambiente. `consume` precisa ser uma única operação
atômica (`GETDEL`, quando suportado, ou script Lua). `GET` seguido de `DEL` não
atende ao contrato.

| Capacidade | Classificação | Observação |
| --- | --- | --- |
| Save/Read | GAP | save está definido; read sem consumo é `MISSING` |
| Consumo atômico | READY | `GETDEL`/Lua pode cumprir o contrato |
| Concorrência | GAP | consumo básico definido; sem revisão/lease/fencing |
| Controle de versão | GAP | schema versionado; revisão física e upcaster ausentes |
| Expiração | GAP | Redis oferece TTL, mas o contrato não define a política |
| Retenção | GAP | expiração da aprovação não define remoção/auditoria |
| Recuperação após restart | GAP | persistence pode ser configurada; claim/receipt ausente |
| Integridade de dados | READY | payload validável; adapter deve proteger transporte e storage |
| Idempotência | GAP | remoção atômica não cobre o efeito externo |

## Decisão

O contrato suporta um adapter Redis mínimo com consumo único, mas o adapter não
pode prometer replay seguro de efeitos externos após crash. A decisão sobre
`DS001-GAP-001` também antecede a implementação Redis.
