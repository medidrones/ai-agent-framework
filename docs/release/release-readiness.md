# Prontidão da candidata 1.0.0rc5

## Decisão

**READY_FOR_STABLE.** A candidata preserva a correção do nome público do
meta-package de `atlas-agent` para `atlas-agent-framework`. O namespace
importável `atlas_agent`, as APIs e o comportamento funcional permanecem
inalterados.

O `rc5` corrige exclusivamente o nome normalizado usado pelo montador do bundle
de evidências. O `rc4` passou pelos gates de qualidade, segurança e matriz, mas
falhou na etapa final ao procurar o arquivo inexistente `atlas_agent-*`.

O nome anterior pertence a um projeto de terceiros no PyPI. A release
`v1.0.0` publicada no GitHub não foi enviada ao registry Python.

## Gates locais

| Gate | Estado | Evidência |
| --- | --- | --- |
| Disponibilidade dos sete nomes no PyPI | PASS | API oficial e simulação de upload |
| Nome legado ausente da metadata pública | PASS | teste de regressão dedicado |
| Workspace e lockfile | PASS | sete distribuições `1.0.0rc5` |
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
| Certificação remota | PASS | workflow `34893053130` |
| Owner sign-offs | PASS | Jorge Medina nos cinco papéis |
| P0/P1 abertas | PASS | `0/0` |

## Próximo gate

1. definir uma estratégia não destrutiva para a tag e GitHub Release `v1.0.0`
   já existentes;
2. executar o gate de promoção estável sem alteração funcional;
3. configurar autenticação protegida do PyPI antes da publicação.

`READY_FOR_STABLE` não autoriza publicação no PyPI nem a movimentação de tags
já publicadas.
