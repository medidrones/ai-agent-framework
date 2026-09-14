# Prontidão da release 1.0.0

## Decisão

**READY_TO_PUBLISH.** A versão estável foi preparada exclusivamente a partir da
candidata certificada `1.0.0rc3`. O delta foi limitado ao versionamento lockstep,
às restrições internas entre os pacotes e à documentação e aos metadados de
release. Nenhuma publicação em registry foi realizada.

## Origem certificada

- candidata: `1.0.0rc3`;
- tag: `v1.0.0rc3`;
- commit: `8177cbda41324039f66698122b128ec9d832f729`;
- certificação técnica: `PASS`;
- cinco owner sign-offs: `PASS`, exercidos por Jorge Medina;
- integridade do bundle do RC: `VERIFIED`;
- digest do bundle: `8d961a13e1dede0a3071420850fda18024eb9283316ecb943d3ca8d51829ad48`;
- P0/P1 abertas: `0/0`;
- alterações materiais após a certificação: `NONE`.

## Gates da promoção

| Gate | Estado | Evidência |
| --- | --- | --- |
| Delta de promoção | PASS | somente versão, documentação e metadados de release |
| Lint e formatação | PASS | Ruff |
| Tipagem | PASS | mypy, 332 arquivos |
| Regressão | PASS | 1.139 testes, cobertura de 93% |
| Segurança estática | PASS | Bandit, zero findings |
| Dependências | PASS | pip-audit, nenhuma vulnerabilidade conhecida |
| Build | PASS | sete wheels e sete sdists |
| Reprodutibilidade | PASS | metadata e manifestos reproduzíveis |
| Instalação limpa | PASS | core, extensões e conjunto completo |
| Smoke dos artefatos | PASS | namespace, `py.typed`, extras e entry points |
| Integridade | PASS | 15 checksums SHA-256 |
| SBOM | PASS | CycloneDX, 79 componentes |
| Segredos nos artefatos | PASS | zero findings em 14 distribuições |
| Exemplos .NET | PASS | REST e gRPC, zero erros e warnings |

## Artefatos

O bundle local em `dist/` contém 14 distribuições `1.0.0`, o SBOM
`atlas-agent-framework.cdx.json` e `SHA256SUMS`. O inventário versionado está em
`reports/release/artifact-security.json`.

## Riscos e limitações

- Os números de performance variam por host e servem apenas como baseline
  relativo.
- A evidência local deverá ser vinculada ao commit de promoção e ao mecanismo
  auditável usado para a release oficial.
- `READY_TO_PUBLISH` não significa `PUBLISHED`; tag, envio ao PyPI e publicação
  da release exigem autorização explícita.
