# Expiração e retenção HITL

O menor deadline efetivo entre request e política de checkpoint encerra a
capacidade. O serviço rejeita `now >= expires_at` antes de persistir decisão; o
backend também impede consumo expirado. Tombstones preservam replay protection
depois do consumo ou purge conforme DS-007/DS-008.

Expiração não aprova, não rejeita e não executa ferramenta implicitamente.
Retenção física e legal hold permanecem responsabilidades das políticas já
certificadas.
