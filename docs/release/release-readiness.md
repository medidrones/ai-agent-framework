# Prontidão da candidata 1.0.1rc1

## Decisão

**READY_FOR_RC.** A candidata inicia a rota não destrutiva para `1.0.1` e
preserva o nome público `atlas-agent-framework`. O namespace importável
`atlas_agent`, as APIs e o comportamento funcional permanecem inalterados.

O conteúdo técnico deriva do `1.0.0rc5`, cuja certificação e sign-offs passaram.
A nova candidata existe para permitir a promoção `1.0.1rc1 → 1.0.1` sem mover
ou reescrever a tag `v1.0.0` já publicada.

O nome anterior pertence a um projeto de terceiros no PyPI. A release
`v1.0.0` publicada no GitHub não foi enviada ao registry Python.

## Gates locais

| Gate | Estado | Evidência |
| --- | --- | --- |
| Disponibilidade dos sete nomes no PyPI | PASS | API oficial e simulação de upload |
| Nome legado ausente da metadata pública | PASS | teste de regressão dedicado |
| Workspace e lockfile | PASS | sete distribuições `1.0.1rc1` |
| Inventário do bundle | PASS | `atlas_agent_framework` coberto por regressão |
| Lint e formatação | PASS | Ruff |
| Tipagem | PASS | mypy, 332 arquivos |
| Regressão | PASS | 1.141 testes, cobertura de 93% |
| Build | PASS | sete wheels e sete sdists |
| Reprodutibilidade | PASS | metadata e manifestos reproduzíveis |
| Instalação limpa | PASS | core, extensões e conjunto completo |
| Namespace e extras | PASS | `atlas_agent`, `py.typed` e entry points |
| Segurança estática | PASS | Bandit, zero findings |
| Dependências | PASS | pip-audit, nenhuma vulnerabilidade conhecida |
| Segredos nos artefatos | PASS | zero findings em 14 distribuições |
| Checksums e SBOM | PASS | 15 checksums; CycloneDX com 79 componentes |
| Exemplos .NET | PASS | REST e gRPC, zero erros e warnings |
| Certificação remota | PENDING | exige tag `v1.0.1rc1` |
| Owner sign-offs | PENDING | após a certificação imutável |
| P0/P1 abertas | PASS | `0/0` na origem certificada |

## Próximo gate

1. criar a tag anotada `v1.0.1rc1` após os gates locais e de `main`;
2. certificar o bundle imutável na matriz remota;
3. registrar novamente os cinco owner sign-offs;
4. executar o gate de promoção para `1.0.1` sem alteração funcional;
5. configurar autenticação protegida do PyPI antes da publicação.

`READY_FOR_RC` não autoriza publicação no PyPI nem a movimentação de tags já
publicadas.
