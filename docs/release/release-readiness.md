# Prontidão da candidata 1.0.1rc2

## Decisão

**READY_FOR_STABLE.** A tag anotada `v1.0.1rc2` concluiu sua certificação
técnica em `PASS` no primeiro attempt. Jorge Medina confirmou separadamente
os cinco owner sign-offs para a nova fonte. A certificação e as aprovações da
`1.0.1rc1` não foram transferidas.

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
| Owner sign-offs | PASS | cinco registros vinculados ao commit RC2 |
| P0/P1 abertas | PASS | issues abertas no GitHub: zero; `0/0` no gate |

O inventário, o digest do manifesto e a identidade da fonte estão preservados
em [evidence/1.0.1rc2/README.md](evidence/1.0.1rc2/README.md). A versão
arquivada da prontidão dentro do bundle da tag representa o estado anterior
à conclusão da própria certificação; o resultado técnico está em
`automated-gates.json` do mesmo bundle. As decisões humanas e a conclusão do
gate estão nos registros versionados posteriores.

## Próximo gate

Executar o gate técnico de promoção `1.0.1rc2 → 1.0.1`, com delta estritamente
limitado a versionamento, metadados e documentação de release. Certificar os
artefatos estáveis instalados antes de qualquer tag ou publicação. A
publicação no PyPI continua dependente de autorização explícita separada.
