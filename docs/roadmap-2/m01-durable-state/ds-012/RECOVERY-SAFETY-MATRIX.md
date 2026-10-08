# Matriz de segurança de recovery

| Situação | Resultado |
| --- | --- |
| checkpoint válido, autorização e ownership verificados | condicionalmente seguro |
| checkpoint consumido/expirado | rejeitar |
| lease ativo de outro owner | conflito |
| lease expirado | adquirir nova geração e revalidar |
| fencing obsoleto | rejeitar |
| HITL pendente/sem decisão | aguardar, sem ferramenta |
| aprovação rejeitada | bloquear |
| terminal/cancelled/deadline vencido | não recuperar |
| payload corrompido/schema incompatível | bloquear/quarentena operacional |
| commit/comando ambíguo | reconciliar antes de decidir |
| efeito externo desconhecido | bloquear retry automático |
| efeito reconciliado | continuar conforme contrato |

As invariantes INV01–INV15 são cobertas pela política DS-012 e pelas regressões de
runtime, stores, leases, HITL, replay, retenção e compatibilidade.
