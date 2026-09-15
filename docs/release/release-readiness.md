# Prontidão da candidata 1.0.1rc2

## Decisão

**NOT_READY.** A candidata `1.0.1rc2` está em preparação e ainda exige
certificação técnica própria, tag imutável e cinco novas aprovações formais.
A certificação e os sign-offs da `1.0.1rc1` não são transferíveis.

O teste temporal que falhou na primeira matriz Windows 3.12 da promoção
`1.0.1` recebeu margem maior. A alteração é restrita ao teste; não modifica
o runtime, a API pública, dependências externas ou os contratos. O histórico
do gate anterior permanece em [STABLE-PROMOTION-STATUS.md](STABLE-PROMOTION-STATUS.md).

## Gates pendentes

| Gate | Estado | Evidência requerida |
| --- | --- | --- |
| Regressão local | PENDENTE | suíte completa e repetição do teste temporal |
| Qualidade remota | PENDENTE | matriz integral, inclusive Windows 3.12 |
| Artefatos | PENDENTE | sete wheels, sete sdists, checksums e SBOM |
| Certificação da tag | PENDENTE | workflow sobre `v1.0.1rc2` |
| Owner sign-offs | NOT_VERIFIED | cinco registros vinculados ao commit RC2 |
| P0/P1 abertas | PENDENTE | confirmação `0/0` no gate |

## Próximo gate

Depois da certificação técnica da `v1.0.1rc2`, coletar separadamente os
cinco sign-offs de Architecture, Engineering, QA, Security e Release Owner.
Somente com todos os gates em `PASS` será possível declarar
`READY_FOR_STABLE` e repetir a promoção para `1.0.1`. A publicação no PyPI
continua dependente de autorização explícita separada.
