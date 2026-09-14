# Gate de aceitação da candidata 1.0.0rc3

Este documento é o gate formal de promoção da `1.0.0rc3` para `1.0.0`.
Cada gate aceita somente `PASS`, `FAIL` ou `NOT_VERIFIED`. Um gate obrigatório
`NOT_VERIFIED` equivale a `FAIL`; qualquer teste obrigatório com falha também
produz `FAIL` automático.

## Gates obrigatórios

| Faixa | Área | Critérios |
| --- | --- | --- |
| RC-01–RC-03 | Release source | tag imutável, versões lockstep e fonte limpa |
| RC-04–RC-08 | Qualidade | Ruff, formatação, mypy, testes e coverage |
| RC-09–RC-12 | Arquitetura | grafo acíclico, neutralidade, import guards e ausência de estado global |
| RC-13–RC-18 | Segurança | P0/P1, canários, dependências, análise estática, identidade e HITL |
| RC-19–RC-25 | Runtime | lifecycle, cancelamento, timeout, retomada, replay, concorrência e cleanup |
| RC-26–RC-32 | Integrações | OpenAI, plugins, MCP, REST, gRPC, mensageria e configuração |
| RC-33–RC-42 | Artefatos | wheels, sdists, metadata, instalação limpa, extras, namespace, typing, entry points, conteúdo e checksums |
| RC-43–RC-47 | Compatibilidade | Python, dependências, contratos, performance e stress |
| RC-48–RC-54 | Documentação | referências, operação, exemplos, .NET, cenário corporativo e changelog |

Os gates RC-33 a RC-42 devem ser executados exclusivamente contra os artefatos
construídos, sem instalação editable ou importação do source tree. O workflow
`Candidata de release` somente monta o bundle depois que a matriz Python
3.12/3.13 em Linux/Windows, segurança e exemplos .NET estiverem aprovados.

## Evidência por gate

| Gates | Evidência verificável |
| --- | --- |
| RC-01–RC-03 | SHA, tag `v1.0.0rc3`, `VERSION`, metadata e `git status` |
| RC-04–RC-08 | logs da CI, `test-summary.json` e `coverage.xml` |
| RC-09–RC-12 | `architecture-audit.json`, testes de arquitetura e import guards |
| RC-13–RC-18 | `security-audit.json`, `dependency-audit.json` e suítes de segurança/HITL |
| RC-19–RC-32 | JUnit das suítes bloqueantes e testes de contrato/integração |
| RC-33–RC-42 | `artifact-inventory.json`, smoke de wheels, SBOM e `SHA256SUMS` |
| RC-43–RC-47 | matriz da CI, `benchmark-report.json` e suíte de stress |
| RC-48–RC-54 | revisão documental, testes dos 22 exemplos e builds .NET |

## Bundle obrigatório

O comando `make rc-evidence`, executado no commit identificado pela tag, produz:

```text
release/1.0.0rc3/
├── automated-gates.json
├── owner-sign-offs.md
├── release-readiness.md
├── test-summary.json
├── coverage.xml
├── architecture-audit.json
├── security-audit.json
├── dependency-audit.json
├── compatibility-matrix.md
├── benchmark-report.json
├── stress-report.json
├── examples-report.json
├── artifact-inventory.json
├── sbom.cdx.json
├── SHA256SUMS
├── wheels/
└── sdists/
```

O bundle é um artefato da CI e não é versionado no Git. O script valida a tag,
anotada, o commit, o working tree, o JUnit, o coverage, as auditorias de
segurança e arquitetura, o
inventário de sete wheels e sete sdists e todos os checksums antes da cópia.
O padrão remoto `v*` deve possuir regra de proteção contra alteração ou exclusão.

## Classificação bloqueante

- **P0 — Critical:** bloqueia RC e Stable imediatamente.
- **P1 — High:** bloqueia a promoção para Stable.
- **P2 — Medium/Low:** somente pode ser aceito quando documentado, com owner e
  follow-up.
- **NOT_VERIFIED:** equivale a `FAIL` para gate obrigatório.

Secret leakage, authorization bypass, efeito antes da aprovação ou
vulnerabilidade P0/P1 não mitigada produzem `FAIL` automático.

## Sign-offs

Architecture, Engineering, QA, Security e Release Engineering devem registrar
uma decisão explícita. O bundle nasce com todos os sign-offs como
`NOT_VERIFIED`: automação técnica não substitui responsabilidade humana.

## Decisão final

`READY_FOR_STABLE` somente pode ser declarado quando todos os gates obrigatórios
forem `PASS`, não houver P0/P1 aberto, o bundle estiver completo, os cinco
sign-offs forem `PASS`, a instalação limpa tiver usado os artefatos reais e
nenhuma alteração material tiver ocorrido depois da certificação.

Até os sign-offs, o resultado permanece:

```text
RC ACCEPTANCE: NOT_VERIFIED
Atlas Agent Framework: NOT_READY
```

Depois da satisfação integral das condições:

```text
RC ACCEPTANCE: PASS
Atlas Agent Framework: READY_FOR_STABLE
Approved target: 1.0.0
```

## Regra de integridade do RC

Qualquer alteração material posterior — código, dependências, metadata,
contratos gerados ou artefatos — invalida a certificação. A correção exige novo
commit, nova versão RC, rebuild e recertificação completa. A versão estável deve
derivar exatamente do RC certificado.
