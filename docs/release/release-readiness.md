# Prontidão da candidata 1.0.1rc2

## Decisão

**NOT_READY.** A tag anotada `v1.0.1rc2` concluiu sua certificação técnica
em `PASS` no primeiro attempt, mas ainda exige cinco novas aprovações formais.
A certificação e os sign-offs da `1.0.1rc1` não são transferíveis.

O teste temporal que falhou na primeira matriz Windows 3.12 da promoção
`1.0.1` recebeu margem maior. A alteração é restrita ao teste; não modifica
o runtime, a API pública, dependências externas ou os contratos. O histórico
do gate anterior permanece em [STABLE-PROMOTION-STATUS.md](STABLE-PROMOTION-STATUS.md).

## Gates

| Gate | Estado | Evidência requerida |
| --- | --- | --- |
| Regressão local | PASS | 1.141 testes, cobertura 93%; teste temporal 20/20 |
| Qualidade remota | PASS | matriz integral na primeira execução, inclusive Windows 3.12 |
| Artefatos | PASS | sete wheels, sete sdists, 15 checksums e SBOM |
| Certificação da tag | PASS | workflow `35010523479` sobre `v1.0.1rc2` |
| Owner sign-offs | NOT_VERIFIED | cinco registros vinculados ao commit RC2 |
| P0/P1 abertas | PENDENTE | confirmação `0/0` no gate humano |

O inventário, o digest do manifesto e a identidade da fonte estão preservados
em [evidence/1.0.1rc2/README.md](evidence/1.0.1rc2/README.md). A versão
arquivada da prontidão dentro do bundle da tag representa o estado anterior
à conclusão da própria certificação; o resultado final está em
`automated-gates.json` do mesmo bundle e nesta atualização posterior.

## Próximo gate

Depois da certificação técnica da `v1.0.1rc2`, coletar separadamente os
cinco sign-offs de Architecture, Engineering, QA, Security e Release Owner.
Somente com todos os gates em `PASS` será possível declarar
`READY_FOR_STABLE` e repetir a promoção para `1.0.1`. A publicação no PyPI
continua dependente de autorização explícita separada.
