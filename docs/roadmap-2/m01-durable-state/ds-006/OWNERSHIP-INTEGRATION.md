# Integração de ownership

O `checkpoint_id` usado no lease é o `execution_id`. Antes de carregar o
payload, o coordinator adquire `CheckpointLease`. A tentativa registra o mesmo
owner e fencing token e só é admitida se essa geração ainda estiver válida.

O consumo HITL passa o lease ao runtime, que exige a capability
`consume_authorized_leased()`. Autorização, validade do lease, fencing e
remoção do checkpoint permanecem atômicos no PostgreSQL.

Depois de um consumo confirmado, a linha de lease pode ser removida por
cascade. A tentativa ainda pode ser concluída quando o checkpoint original,
identificado por seu digest opaco, já não existe e a tentativa comprova a mesma
geração. Se o checkpoint ainda existe, a conclusão exige o lease vigente.
