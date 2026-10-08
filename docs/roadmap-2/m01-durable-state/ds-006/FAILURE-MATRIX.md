# Matriz de falhas

| Falha | Comportamento |
| --- | --- |
| Descoberta indisponível | lote falha; nenhuma decisão é fabricada |
| Precheck lança erro | candidato `FAILED`; lote continua |
| Conflito de lease | candidato `CONFLICT` |
| Payload inválido/incompatível | candidato `BLOCKED` |
| Timeout do invoker | `FAILED / recovery_timeout` |
| Invoker falha | `FAILED / recovery_failed` |
| Persistência do resultado falha | nunca reporta `RECOVERED` |
| Lease expira durante recovery | `CONFLICT / lease_lost` |
| Cancelamento | tenta registrar `cancelled`, libera lease e propaga |
| Observabilidade falha | execução continua por contrato fail-open |
| Efeito externo de resultado desconhecido | não repetir automaticamente |

O release do lease é best effort apenas para a geração corrente. Um owner
obsoleto não pode renovar, consumir ou concluir uma tentativa protegida.
