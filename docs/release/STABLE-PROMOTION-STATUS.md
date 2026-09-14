# Atlas Agent Framework — Status da promoção estável

## Escopo

Promoção administrativa de `1.0.0rc3` para `1.0.0`, sem nova funcionalidade,
refactoring ou alteração de API, dependência externa, arquitetura, contrato,
schema, configuração, workflow ou política de segurança.

## Fonte certificada

| Campo | Valor |
| --- | --- |
| RC | `1.0.0rc3` |
| Tag | `v1.0.0rc3` |
| Commit certificado | `8177cbda41324039f66698122b128ec9d832f729` |
| Status técnico | `PASS` |
| Owner sign-offs | `PASS` |
| Responsável pelos cinco papéis | Jorge Medina |
| Integridade do artefato do RC | `VERIFIED` |
| Alterações materiais | `NONE` |
| P0/P1 abertas | `0/0` |

O SHA acima é o objeto efetivamente apontado pela tag anotada `v1.0.0rc3`. Ele
corrige a transposição presente no valor textual
`8177cbd4a1324039f66698122b128ec9d832f729`, que não identifica um objeto Git
válido neste repositório.

## Delta autorizado

As diferenças entre a fonte certificada e a versão estável são restritas a:

- remoção do sufixo `rc3` em `VERSION` e nos sete módulos de versão;
- atualização lockstep das restrições internas entre os sete pacotes;
- changelog, README, notas, evidências e relatórios de release;
- inventário, checksums e SBOM dos novos artefatos.

Não há alteração em implementação funcional, API pública, dependência externa,
arquitetura, schema, wire contract, política de segurança ou testes.

## Certificação dos artefatos estáveis

| Verificação | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| `ruff check` | PASS |
| `ruff format --check` | PASS |
| `mypy packages` | PASS — 332 arquivos |
| suíte de regressão | PASS — 1.139 testes, 93% de cobertura |
| build reproduzível | PASS — 14 distribuições |
| validação de metadata | PASS |
| instalação limpa sem editable | PASS |
| namespace e `py.typed` | PASS |
| extras e plugin entry points | PASS |
| Bandit | PASS — zero findings |
| pip-audit | PASS — nenhuma vulnerabilidade conhecida |
| scanner de segredos | PASS — zero findings em 14 distribuições |
| checksums SHA-256 | PASS — 15 entradas |
| SBOM CycloneDX | PASS — 79 componentes |
| exemplos .NET REST e gRPC | PASS — zero erros e warnings |

Os artefatos certificados permanecem locais em `dist/`. Nenhum pacote foi
enviado ao PyPI ou a outro registry.

## Decisão final

```text
STABLE PROMOTION       PASS
SOURCE RC              1.0.0rc3
TARGET                 1.0.0
RC COMMIT              8177cbda41324039f66698122b128ec9d832f729
OWNER SIGN-OFFS        PASS
P0 OPEN                0
P1 OPEN                0
PROMOTION DELTA        VERIFIED
STABLE ARTIFACTS       VERIFIED
CLEAN INSTALL          PASS
SMOKE TESTS            PASS
ARTIFACT SECRET SCAN   PASS

FINAL DECISION         READY_TO_PUBLISH
```

`READY_TO_PUBLISH` não significa `PUBLISHED`. A criação da tag estável e a
publicação oficial permanecem ações separadas, sujeitas a autorização explícita.
