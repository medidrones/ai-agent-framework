# Elegibilidade para purge

Resultados possíveis: não elegível, elegível, bloqueado por lease, recovery,
retenção ou política. Incompatibilidade, legal hold e prazo indefinido falham de
forma fechada. `ELIGIBLE` é somente um fato auditável; não autoriza nem executa
remoção. O purge completo e seus controles operacionais pertencem à DS-008.

O método físico legado `purge_expired()` permanece disponível somente no modo
1.x sem política DS-007. Com `retention_policy`, ele falha explicitamente.
