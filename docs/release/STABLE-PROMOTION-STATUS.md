# Atlas Agent Framework — Gate de promoção estável 1.0.1

## Origem certificada

| Campo | Valor |
| --- | --- |
| RC | `1.0.1rc1` |
| Tag | `v1.0.1rc1` |
| Commit certificado | `16d1c4d26868cec65ca9385bc76f9e9db8f81d97` |
| Workflow de certificação | [34896013098](https://github.com/medidrones/ai-agent-framework/actions/runs/34896013098) |
| Owner sign-offs | `PASS`, Jorge Medina nos cinco papéis |
| Integridade do RC | `VERIFIED`, 14 artefatos e 15 checksums |
| Alterações materiais após o RC | `NONE` |
| P0/P1 abertas | `0/0` |

As aprovações formais estão em
[`docs/release/evidence/1.0.1rc1/`](evidence/1.0.1rc1/README.md).
As tags `v1.0.0` e `v1.0.1rc1` permanecem imutáveis.

## Delta de promoção autorizado

- remoção do sufixo `rc1` em `VERSION` e nos sete módulos de versão;
- atualização lockstep das restrições internas dos sete pacotes;
- changelog, README, compatibilidade, notas e evidências de release;
- novos wheels, sdists, checksums e SBOM específicos de `1.0.1`.

O comparador dos wheels encontrou **zero diferenças funcionais em 221 membros
de payload** após excluir os módulos de versão e a metadata gerada. Para as
sete distribuições, `Name`, `Requires-Python` e `Requires-Dist` coincidiram
após normalizar apenas `1.0.1rc1 → 1.0.1`. Não houve mudança em código de
runtime, API, dependências externas, arquitetura, schemas, wire contracts,
políticas de segurança ou testes.

## Certificação local dos artefatos estáveis

| Verificação | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| Ruff lint e formato | PASS |
| mypy | PASS — 332 arquivos |
| Regressão | PASS — 1.141 testes, 93% de cobertura |
| Build | PASS — sete wheels e sete sdists |
| Metadata, licença, `py.typed` e entry points | PASS |
| Reprodutibilidade de metadata e manifestos | PASS |
| Instalação limpa, sem editable | PASS — core, base e full |
| Namespace, extras e imports opcionais | PASS |
| Auditoria de arquitetura e API | PASS |
| Bandit | PASS — zero findings |
| pip-audit | PASS — nenhuma vulnerabilidade conhecida |
| Scanner de segredos | PASS — zero findings em 14 artefatos |
| SHA-256 | PASS — 15 entradas verificadas |
| SBOM CycloneDX | PASS — versão `1.0.1`, 79 componentes |
| Exemplos .NET REST e gRPC | PASS — zero erros e avisos |
| Matriz remota do commit estável | PENDING |

Os artefatos e relatórios desta etapa estão locais em `dist/` e
`reports/release/`. Os artefatos antigos foram preservados em
`release/archived-dist-before-1.0.1/`. Nenhum pacote foi enviado ao PyPI.

## Decisão provisória

```text
STABLE PROMOTION       PENDING
SOURCE RC              1.0.1rc1
TARGET                 1.0.1
OWNER SIGN-OFFS        PASS
P0/P1 OPEN             0/0
PROMOTION DELTA        VERIFIED
LOCAL ARTIFACTS        VERIFIED
REMOTE CERTIFICATION   PENDING

FINAL DECISION         NOT_READY_TO_PUBLISH
```

O gate será fechado somente após a matriz remota da fonte estável passar.
`READY_TO_PUBLISH` não significa `PUBLISHED`: tag estável, GitHub Release e
publicação no PyPI continuam etapas separadas. O envio ao PyPI exige
autorização explícita e autenticação protegida.
