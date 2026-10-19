# Atlas Agent Framework — Gate de promoção estável 1.1.0

## Decisão

**PUBLISHED.** A candidata `1.1.0rc2` está certificada e aprovada por
cinco owner sign-offs. Os artefatos da versão estável `1.1.0` passaram nos
gates locais e remotos no primeiro attempt e foram publicados sem rebuild.

## Fonte congelada

- RC: `1.1.0rc2`
- Tag anotada: `v1.1.0rc2`
- Commit certificado: `fd91bad8d6919a46504ba7fa45fee02fc9e21d52`
- Certificação: [workflow 38974750546](https://github.com/medidrones/ai-agent-framework/actions/runs/38974750546), `PASS`
- Owner sign-offs: cinco `PASS` de Jorge Medina,
  [registrados individualmente](evidence/1.1.0rc2/SIGN-OFF-STATUS.md)
- P0/P1 abertas: `0/0` no gate de sign-offs
- Integridade do RC: `VERIFIED`, sete wheels, sete sdists e 15 checksums

## Delta autorizado

- `1.1.0rc2 → 1.1.0` nas versões e restrições internas lockstep;
- sincronização do lockfile sem alterar dependências externas;
- documentação, changelog e metadados de release;
- novos artefatos, checksums e SBOM para `1.1.0`.

São proibidas mudanças funcionais, de API ou contratos, dependências externas,
arquitetura, schemas, wire contracts, política de segurança, workflows e
desativação de testes.

Nenhum arquivo funcional ou teste foi alterado entre a tag `v1.1.0rc2` e o
commit de preparação estável; somente versões, restrições internas e
documentação de release mudaram.

## Fonte e integridade da versão estável

- Commit do build estável: `116e886e95c8785920ca1f18e6d88b01a3c1e3ed`
- [Qualidade remota](https://github.com/medidrones/ai-agent-framework/actions/runs/39056283970): attempt 1, `PASS` em Ubuntu/Windows 3.12/3.13, PostgreSQL, Redis, segurança e exemplos .NET
- [Empacotamento remoto](https://github.com/medidrones/ai-agent-framework/actions/runs/39056283924): attempt 1, `PASS` para build, reprodutibilidade, instalações limpas e Python 3.12/3.13
- Bundle arquivado: `atlas-release-candidate`, artefato ID `12109697194`
- Digest do bundle: `sha256:2f14fcc012db1d15893e9e637af86426478938e54238141faa7736d3dccd730c`
- SHA-256 do `SHA256SUMS` remoto: `688dbcb587d654defeb893b03dbd48ac7aaec835e577e9d3473dbc770778b1eb`
- Inventário remoto: sete wheels, sete sdists e 15/15 checksums verificados
- SBOM CycloneDX 1.6: versão `1.1.0`, 84 componentes
- Grafo de dependências: zero ciclos; artifact secret scan: zero findings
- Delta do payload remoto: 251 membros funcionais idênticos em sete wheels;
  sete módulos de versão diferem apenas em `1.1.0rc2 → 1.1.0`
- Metadata: `Name`, `Requires-Python`, dependências e entry points coincidem
  após normalizar exclusivamente o sufixo de versão

A certificação e a publicação vinculam-se **exatamente** aos artefatos do commit
`116e886e95c8785920ca1f18e6d88b01a3c1e3ed` arquivados no workflow
`39056283924`. Este commit documental posterior não é a fonte dos artefatos.
A tag estável aponta ao commit certificado; qualquer build sobre outro commit
precisará passar novamente pelo gate de artefatos.

## Evidências de publicação

- Tag anotada e GitHub Release:
  [`v1.1.0`](https://github.com/medidrones/ai-agent-framework/releases/tag/v1.1.0)
- Lote fundação: [workflow 39162729764](https://github.com/medidrones/ai-agent-framework/actions/runs/39162729764), `PASS`
- Lote integrações: [workflow 39162933353](https://github.com/medidrones/ai-agent-framework/actions/runs/39162933353), `PASS`
- Lote final: [workflow 39244325275](https://github.com/medidrones/ai-agent-framework/actions/runs/39244325275), `PASS`
- Autenticação: Trusted Publishing via OIDC e ambientes protegidos individuais
- PyPI: sete projetos, sete wheels, sete sdists e 14/14 hashes confirmados

## Certificação local

| Gate | Resultado |
| --- | --- |
| `uv sync --locked` | `PASS` |
| Ruff lint e formato | `PASS` — 813 arquivos formatados |
| mypy | `PASS` — 376 arquivos |
| Regressão | `PASS` — 1.456 testes, zero skips/falhas e cobertura 92,68% |
| PostgreSQL 16 e Redis 7.4 reais | `PASS` |
| Build | `PASS` — sete wheels e sete sdists |
| Metadata, licença, `py.typed` e entry points | `PASS` |
| Reprodutibilidade de metadata e manifestos | `PASS` |
| Instalação limpa, sem editable | `PASS` — core, extensões e full |
| Namespace e extras | `PASS` |
| Auditoria de arquitetura e API | `PASS` — zero ciclos |
| Bandit e dependências | `PASS` — zero findings e vulnerabilidades conhecidas |
| Scanner de segredos | `PASS` — zero findings em 14 artefatos |
| SHA-256 | `PASS` — 15/15 entradas |
| SBOM | `PASS` — CycloneDX 1.6, versão `1.1.0`, 84 componentes |
| Exemplos .NET REST e gRPC | `PASS` — zero erros e avisos |
| Delta RC–estável | `PASS` — 251 membros funcionais idênticos |

O SHA-256 local do manifesto `SHA256SUMS` é
`936a3285e5da2007c780918c2920538dcbaa41e239df97ec3a9fd43313792f23`.
A metadata das sete distribuições coincide após normalizar exclusivamente
`1.1.0rc2 → 1.1.0`.

O montador `assemble_rc_evidence.py` não integra este gate porque valida
explicitamente apenas versões com sufixo RC. Seus gates precedentes — build,
reprodutibilidade, smoke tests, auditorias, SBOM, checksums, Bandit e
`pip-audit` — foram executados individualmente com sucesso.

## Gate final

```text
STABLE PROMOTION       PASS
SOURCE RC              1.1.0rc2
TARGET                 1.1.0
RC COMMIT              fd91bad8d6919a46504ba7fa45fee02fc9e21d52
STABLE BUILD COMMIT    116e886e95c8785920ca1f18e6d88b01a3c1e3ed
OWNER SIGN-OFFS        PASS
P0/P1 OPEN             0/0
PROMOTION DELTA        VERIFIED
STABLE ARTIFACTS       VERIFIED
CLEAN INSTALL          PASS
SMOKE TESTS            PASS
ARTIFACT SECRET SCAN   PASS

FINAL DECISION         PUBLISHED
```

Os avisos de depreciação do Node.js 20 nas GitHub Actions e de futura migração
do runner `ubuntu-latest` foram classificados como não bloqueantes. A tag,
a GitHub Release e os uploads no PyPI foram concluídos com autorização formal
de Jorge Medina.
