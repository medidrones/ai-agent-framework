# Políticas de retenção

`CheckpointRetentionPolicy` possui janelas separadas para consumido, expirado,
terminal e recovery, além de TTL ativo/HITL, versão, retenção mínima e legal
hold. Durações nulas ou negativas e retenções abaixo do mínimo são rejeitadas.

O prazo efetivo é `max(prazo_persistido, início + política_atual)`. Logo,
expansões são conservadoras e reduções não apagam dados antecipadamente.
