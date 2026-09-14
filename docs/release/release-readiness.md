# Prontidão da candidata 1.0.1rc1

## Decisão

**READY_FOR_STABLE.** A candidata concluiu a certificação técnica e o gate
formal de aprovações para a rota não destrutiva até `1.0.1`. Ela
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
| Certificação remota | PASS | workflow `34896013098` sobre `v1.0.1rc1` |
| Owner sign-offs | PASS | cinco papéis aprovados por Jorge Medina |
| P0/P1 abertas | PASS | `0/0` na origem certificada |

## Próximo gate

1. executar o gate de promoção para `1.0.1` sem alteração funcional;
2. construir e certificar os artefatos estáveis derivados do RC;
3. configurar autenticação protegida do PyPI antes da publicação;
4. exigir autorização explícita separada para publicar no registry.

`READY_FOR_STABLE` não autoriza publicação no PyPI nem a movimentação de tags já
publicadas.
