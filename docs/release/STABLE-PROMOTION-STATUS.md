# Atlas Agent Framework — Gate de promoção estável 1.0.1

## Decisão

**READY_TO_PUBLISH.** A candidata `1.0.1rc2` está certificada e aprovada por
cinco owner sign-offs. Os artefatos da versão estável `1.0.1` passaram nos
gates locais e remotos no primeiro attempt. Isso não significa `PUBLISHED` e
não autoriza, por si só, envio ao PyPI.

## Fonte congelada

- RC: `1.0.1rc2`
- Tag anotada: `v1.0.1rc2`
- Commit certificado: `31ccac66c0fc2002fe908e68e40a07c95f684c72`
- Certificação: [workflow 35010523479](https://github.com/medidrones/ai-agent-framework/actions/runs/35010523479), attempt 1, `PASS`
- Owner sign-offs: cinco `PASS` de Jorge Medina,
  [registrados individualmente](evidence/1.0.1rc2/SIGN-OFF-STATUS.md)
- P0/P1 abertas: `0/0` no gate de sign-offs
- Integridade do RC: `VERIFIED`, 14 artefatos, 15 checksums

## Delta autorizado

- `1.0.1rc2 → 1.0.1` em versões e restrições internas lockstep;
- documentação, changelog e metadados de release;
- novos artefatos, checksums e SBOM para `1.0.1`.

São proibidos mudanças funcionais, API/contratos, dependências externas,
arquitetura, política de segurança, workflows e desativação de testes.

O [relatório da tentativa anterior](history/STABLE-PROMOTION-STATUS-1.0.1rc1.md)
permanece preservado. Nenhum arquivo funcional ou teste foi alterado entre a
tag `v1.0.1rc2` e o commit de preparação estável; só versões, restrições
internas e documentação de release mudaram.

## Fonte e integridade da versão estável

- Commit do build estável: `43fd7008f8573f2b2a9906ee8c257986777f04e9`
- [Qualidade remota](https://github.com/medidrones/ai-agent-framework/actions/runs/35017413640): attempt 1, `PASS` em Ubuntu/Windows 3.12/3.13, segurança e exemplos .NET
- [Empacotamento remoto](https://github.com/medidrones/ai-agent-framework/actions/runs/35017413644): attempt 1, `PASS` para build, reprodutibilidade, instalações limpas e Python 3.12/3.13
- Bundle arquivado: `atlas-release-candidate`, artefato ID `10416406388`
- SHA-256 do `SHA256SUMS` remoto: `5931aa6a6a66c923831cae1dfeba96571eb10fb812c1cd8816fd0d707aa1094d`
- Inventário remoto: 7 wheels, 7 sdists, 15/15 checksums verificados
- SBOM CycloneDX: versão `1.0.1`, 79 componentes
- Grafo de dependências: zero ciclos; artifact secret scan: zero findings
- Delta do payload remoto: 221 membros funcionais idênticos em sete wheels;
  sete módulos de versão diferem apenas em `1.0.1rc2 → 1.0.1`
- Metadata: `Name`, `Requires-Python`, dependências e entry points coincidem
  após normalizar exclusivamente o sufixo de versão

A decisão `READY_TO_PUBLISH` vincula-se **exatamente** aos artefatos do commit
`43fd7008f8573f2b2a9906ee8c257986777f04e9` arquivados no workflow
`35017413644`. O commit posterior que registra este relatório modifica apenas
documentação; ele não é a fonte dos artefatos certificados. Uma futura tag
estável deve apontar ao commit certificado, ou qualquer novo build sobre outro
commit deverá passar novamente pelo gate de artefatos antes de publicação.

## Certificação local

| Gate | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| Ruff lint e formato | PASS |
| mypy | PASS — 332 arquivos |
| Regressão | PASS — 1.141 testes, 93% de cobertura |
| Build | PASS — sete wheels e sete sdists |
| Metadata, licença, `py.typed` e entry points | PASS |
| Reprodutibilidade de metadata e manifestos | PASS |
| Instalação limpa, sem editable | PASS — core, base e full |
| Namespace e extras | PASS |
| Auditoria de arquitetura e API | PASS |
| Bandit e dependências | PASS — zero findings e zero vulnerabilidades conhecidas |
| Scanner de segredos | PASS — zero findings em 14 artefatos |
| SHA-256 | PASS — 15/15 entradas |
| SBOM | PASS — `1.0.1`, 79 componentes |
| Exemplos .NET REST e gRPC | PASS — zero erros e avisos |
| Delta RC–estável local | PASS — 221 membros funcionais idênticos |

Os builds locais de `1.0.1` estão em `dist/`. Os 16 arquivos locais da RC2
foram preservados em `release/archived-dist-1.0.1rc2-before-stable/`, sem
mistura com o novo inventário. A evidência técnica remota foi inspecionada em
`release/inspection-stable-1.0.1-rc2-promotion/`.

## Gate final

```text
STABLE PROMOTION       PASS
SOURCE RC              1.0.1rc2
TARGET                 1.0.1
RC COMMIT              31ccac66c0fc2002fe908e68e40a07c95f684c72
STABLE BUILD COMMIT    43fd7008f8573f2b2a9906ee8c257986777f04e9
OWNER SIGN-OFFS        PASS
P0/P1 OPEN             0/0
PROMOTION DELTA        VERIFIED
STABLE ARTIFACTS       VERIFIED
CLEAN INSTALL          PASS
SMOKE TESTS            PASS
ARTIFACT SECRET SCAN   PASS

FINAL DECISION         READY_TO_PUBLISH
```

Os avisos de depreciação do Node.js 20 nas GitHub Actions e um aviso local de
cache do pytest foram não bloqueantes. Não foram criados tag `v1.0.1`, GitHub
Release ou upload no PyPI. Essas ações pertencem ao ciclo separado de
publicação oficial e exigem autorização explícita.
