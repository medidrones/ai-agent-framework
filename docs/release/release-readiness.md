# Prontidão da candidata 1.0.0rc4

## Decisão

**READY_FOR_RC.** A candidata corrige o nome público do meta-package de
`atlas-agent` para `atlas-agent-framework`. O namespace importável
`atlas_agent`, as APIs e o comportamento funcional permanecem inalterados.

O nome anterior pertence a um projeto de terceiros no PyPI. A release
`v1.0.0` publicada no GitHub não foi enviada ao registry Python.

## Gates locais

| Gate | Estado | Evidência |
| --- | --- | --- |
| Disponibilidade dos sete nomes no PyPI | PASS | API oficial e simulação de upload |
| Nome legado ausente da metadata pública | PASS | teste de regressão dedicado |
| Workspace e lockfile | PASS | sete distribuições `1.0.0rc4` |
| Lint e formatação | PASS | Ruff |
| Tipagem | PASS | mypy, 332 arquivos |
| Regressão | PASS | 1.140 testes, cobertura de 93% |
| Build | PASS | sete wheels e sete sdists |
| Reprodutibilidade | PASS | metadata e manifestos reproduzíveis |
| Instalação limpa | PASS | core, extensões e conjunto completo |
| Namespace e extras | PASS | `atlas_agent`, `py.typed` e entry points |
| Segurança estática | PASS | Bandit, zero findings |
| Dependências | PASS | pip-audit, nenhuma vulnerabilidade conhecida |
| Segredos nos artefatos | PASS | zero findings em 14 distribuições |
| Checksums e SBOM | PASS | 15 checksums; CycloneDX com 79 componentes |
| Exemplos .NET | PASS | REST e gRPC, zero erros e warnings |

## Próximo gate

1. criar a tag anotada `v1.0.0rc4` somente após autorização;
2. certificar o bundle imutável na matriz remota;
3. registrar novamente os cinco owner sign-offs;
4. definir a estratégia para substituir a tag/release `v1.0.0` existente;
5. configurar autenticação protegida do PyPI antes da promoção final.

`READY_FOR_RC` não autoriza publicação no PyPI.
