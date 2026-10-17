# Atlas Agent Framework — Gate de promoção estável 1.1.0

## Estado

**IN_PROGRESS.** A candidata `1.1.0rc2` está certificada e aprovada por cinco
owner sign-offs. A promoção exige certificação específica dos artefatos
`1.1.0` antes de qualquer decisão `READY_TO_PUBLISH`.

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

## Decisão intermediária

Os gates locais estão em `PASS`. A decisão permanece `IN_PROGRESS` até que os
workflows remotos de qualidade e empacotamento certifiquem exatamente o commit
de preparação estável. Não há tag estável, GitHub Release ou envio ao PyPI.
