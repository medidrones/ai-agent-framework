# Atlas Agent Framework 1.0.1 — Estado da publicação

## Decisão

**PUBLICAÇÃO PARCIAL VERIFICADA (3/7).** O gate técnico da versão estável está
`READY_TO_PUBLISH`. O lote autorizado `fundacao` foi publicado, com os seis
hashes dos três projetos conferidos contra o manifesto certificado. A GitHub
Release permanece em rascunho. Não marcar o release completo como `PUBLISHED`
até verificar os sete projetos, os 14 arquivos e publicar o rascunho.

## Fonte imutável

- Tag anotada: `v1.0.1`
- Commit apontado pela tag: `43fd7008f8573f2b2a9906ee8c257986777f04e9`
- [Gate técnico](STABLE-PROMOTION-STATUS.md): `PASS`, decisão
  `READY_TO_PUBLISH`
- Bundle certificado: workflow [35017413644](https://github.com/medidrones/ai-agent-framework/actions/runs/35017413644), artefato ID `10416406388`
- SHA-256 do manifesto `SHA256SUMS`:
  `5931aa6a6a66c923831cae1dfeba96571eb10fb812c1cd8816fd0d707aa1094d`

## GitHub

- Tag `v1.0.1`: `PUSHED`, sem mover tags anteriores.
- GitHub Release ID `389449556`: `DRAFT`, associada à tag e ao commit
  certificado.
- Assets: 7 wheels, 7 sdists, `SHA256SUMS` e SBOM CycloneDX.
- Integridade: 16/16 digests SHA-256 dos assets do GitHub coincidem com os
  arquivos do bundle certificado.
- Release pública: `NOT_PUBLISHED`.
- Lote `fundacao`: [execução manual 35027170998](https://github.com/medidrones/ai-agent-framework/actions/runs/35027170998)
  `SUCCESS` após revisão humana dos três environments. O primeiro job conferiu
  fonte, run, artefato e inventário do bundle certificado.
- O token `GITHUB_TOKEN` com `contents: read` do gate não conseguiu consultar
  o rascunho da Release (`HTTP 403` em duas execuções sem upload). O estado
  `DRAFT`, a tag, o commit e os 16 assets foram conferidos separadamente pela
  conta autorizada antes de iniciar o lote. O gate do workflow permanece
  limitado a fonte, run, artefato certificado e hashes, sem ampliar a
  permissão para `contents: write`.

## PyPI

- Antes da publicação, os sete nomes `atlas-agent-framework`, `atlas-agent-adapters`,
  `atlas-agent-config`, `atlas-agent-core`, `atlas-agent-evaluation`,
  `atlas-agent-mcp` e `atlas-agent-providers` retornaram `404` no endpoint
  oficial de projetos do PyPI na consulta de 2026-09-15.
- O dry-run do `uv publish` conferiu 14 distribuições exatas do bundle.
- Não havia `UV_PUBLISH_TOKEN`, credenciais Twine/PyPI ou `.pypirc` neste
  ambiente; nenhuma credencial estática será necessária para o canal escolhido.
- Trusted Publishing tentou obter identidade OIDC, mas esta execução local
  não é um ambiente suportado para emitir o token.
- O workflow manual
  [`publish-pypi.yml`](../../.github/workflows/publish-pypi.yml) revalida o
  bundle certificado sem OIDC. A execução manual seleciona um dos lotes
  fixos `fundacao` (core, adapters, config), `integracoes` (evaluation,
  framework, mcp) ou `final` (providers); cada distribuição é publicada em
  um job separado, com environment protegido próprio. Os lotes posteriores
  exigem os dois hashes de cada projeto anterior no PyPI. O environment
  `pypi` é exclusivo do core.
- Os Pending Publishers iniciais de `atlas-agent-core`,
  `atlas-agent-adapters` e `atlas-agent-config` foram convertidos em
  publicadores ativos após os uploads. A conta `medicode` reconfirmou a senha
  para ações sensíveis; a interface autenticada mostrou exatamente esses três
  projetos ativos e nenhum Pending Publisher. Com os slots liberados e a
  confirmação específica do responsável, foram registrados e conferidos os
  Pending Publishers de `atlas-agent-evaluation` (`pypi-evaluation`),
  `atlas-agent-framework` (`pypi-framework`) e `atlas-agent-mcp` (`pypi-mcp`),
  todos com owner `medidrones`, repositório `ai-agent-framework` e workflow
  `publish-pypi.yml`. `atlas-agent-providers` ainda não foi registrado.
- Os três novos environments GitHub exigem revisão de `medidrones` e
  permitem deploy somente em `main`; a configuração foi conferida antes de
  considerar os registros prontos para o lote seguinte.
- Os sete environments GitHub existem, exigem aprovação de `medidrones` e
  permitem deploy apenas em `main`. O workflow seletivo está `ACTIVE` no
  GitHub; Qualidade e Empacotamento do commit `3074a4e92421d986e7a106828ec1208a7612767a`
  passaram. A execução bem-sucedida usou o commit de workflow
  `7f70a5517956f84a78db5b3f2a6942b5f492766f`, sem mover a tag estável.
- Upload `fundacao`: `SUCCESS`. As duas execuções anteriores falharam na
  consulta ao rascunho com `HTTP 403`, antes de qualquer upload; o gate foi
  ajustado mantendo permissões mínimas e o rascunho foi conferido pela conta
  autorizada antes da execução bem-sucedida.
- SHA-256 `VERIFIED` para os wheels e sdists dos três projetos:
  `atlas_agent_core` (`2a1cd36c…`, `d77036e4…`),
  `atlas_agent_adapters` (`4a123ff5…`, `8aa8281d…`) e
  `atlas_agent_config` (`3d28b6f3…`, `c918c251…`). O endpoint JSON oficial
  do PyPI retornou exatamente dois arquivos para cada versão `1.0.1`, com
  nome e digest idênticos ao `SHA256SUMS` certificado.

## Próxima ação

Solicitar decisão explícita de publicação para o lote `integracoes`. O
registro dos três novos Pending Publishers não autoriza o primeiro upload.
Cada projeto usa um environment GitHub próprio para distinguir sua identidade
OIDC:

| Projeto PyPI | Environment | Versão 1.0.1 | Publisher |
| --- | --- | --- | --- |
| `atlas-agent-core` | `pypi` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-adapters` | `pypi-adapters` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-config` | `pypi-config` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-evaluation` | `pypi-evaluation` | `NOT_PUBLISHED` | `PENDING_REGISTERED` |
| `atlas-agent-framework` | `pypi-framework` | `NOT_PUBLISHED` | `PENDING_REGISTERED` |
| `atlas-agent-mcp` | `pypi-mcp` | `NOT_PUBLISHED` | `PENDING_REGISTERED` |
| `atlas-agent-providers` | `pypi-providers` | `NOT_PUBLISHED` | `NOT_REGISTERED` |

O [formulário de Pending Publisher](https://pypi.org/manage/account/publishing/)
é preenchido pela conta PyPI responsável. Essa configuração não cria nem
reserva um projeto antes do primeiro upload. O próprio PyPI informou o limite
de três publicadores pendentes simultâneos por conta. A publicação controlada
em lotes foi autorizada; o primeiro upload de cada projeto deve converter o
publicador pendente em ativo e liberar espaço. A interface autenticada
confirmou essa conversão para `fundacao`. A autorização de upload atual
abrangeu somente `fundacao`, não os lotes subsequentes.
Nenhum lote deve publicar a GitHub Release em rascunho antes da
verificação dos sete projetos e dos 14 hashes. Não inserir tokens em
documentação, commit, issue ou conversa.
