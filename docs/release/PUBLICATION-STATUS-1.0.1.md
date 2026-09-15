# Atlas Agent Framework 1.0.1 — Estado da publicação

## Decisão

**PUBLICAÇÃO COMPLETA VERIFICADA.** O gate técnico da versão estável passou.
Os três lotes autorizados foram publicados no PyPI e os nomes e SHA-256 dos
14 arquivos dos sete projetos coincidem com o manifesto certificado. Após
autorização separada, a GitHub Release `v1.0.1` também foi publicada com os
16 assets íntegros. Estado final: `PUBLISHED` nos dois canais.

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
- [GitHub Release `v1.0.1`](https://github.com/medidrones/ai-agent-framework/releases/tag/v1.0.1),
  ID `389449556`: `PUBLISHED` em `2026-09-15T22:11:56Z`, associada à tag e
  ao commit certificado; `prerelease=false`.
- Assets: 7 wheels, 7 sdists, `SHA256SUMS` e SBOM CycloneDX.
- Integridade: 16/16 digests SHA-256 dos assets do GitHub coincidem com os
  arquivos do bundle certificado.
- Release pública: `PUBLISHED`; após a publicação, 16/16 digests SHA-256 dos
  assets foram novamente conferidos, sem alteração da tag ou do commit.
- Lote `fundacao`: [execução manual 35027170998](https://github.com/medidrones/ai-agent-framework/actions/runs/35027170998)
  `SUCCESS` após revisão humana dos três environments. O primeiro job conferiu
  fonte, run, artefato e inventário do bundle certificado.
- Lote `integracoes`: [execução manual 35028290526](https://github.com/medidrones/ai-agent-framework/actions/runs/35028290526)
  `SUCCESS` após revisão humana de `pypi-evaluation`, `pypi-framework` e
  `pypi-mcp`. O primeiro job conferiu também os seis hashes do lote anterior
  no PyPI antes de permitir esses uploads.
- Lote `final`: [execução manual 35028969660](https://github.com/medidrones/ai-agent-framework/actions/runs/35028969660)
  `SUCCESS` após revisão humana de `pypi-providers`. Os jobs de verificação
  e publicação terminaram com sucesso, sem deployment pendente. A conferência
  posterior no endpoint JSON oficial do PyPI encontrou 14/14 nomes e hashes
  iguais aos do manifesto certificado.
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
- Os Pending Publishers foram registrados em três lotes, respeitando o limite
  de três pendentes simultâneos por conta. Os uploads converteram todos os
  sete registros em publicadores ativos. A interface autenticada da conta
  `medicode` mostrou os sete projetos ativos e nenhum Pending Publisher após
  o lote `final`.
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
- Upload `integracoes`: `SUCCESS`. Os wheels e sdists de
  `atlas_agent_evaluation` (`16d6b642…`, `f7b8bbc1…`),
  `atlas_agent_framework` (`0ebc697e…`, `e5905eec…`) e
  `atlas_agent_mcp` (`571269eb…`, `ea09f4c3…`) foram comparados com o
  endpoint JSON oficial do PyPI: dois nomes e dois SHA-256 exatos por projeto,
  iguais ao manifesto certificado.
- Upload `final`: `SUCCESS`. O wheel e o sdist de `atlas_agent_providers`
  (`c0275438…`, `107d0924…`) foram comparados com o endpoint JSON oficial
  do PyPI: dois nomes e dois SHA-256 exatos, iguais ao manifesto certificado.
  A conferência conjunta dos sete projetos retornou `14/14 HASH_VERIFIED`.

## Encerramento

O responsável autorizou separadamente a publicação da GitHub Release. Antes
da ação, foram reconfirmados tag, commit, notas e 16/16 digests; a frase
obsoleta sobre upload pendente no PyPI foi substituída nas notas públicas.
A consulta posterior confirmou `draft=false`, URL pública, tag e commit
certificados, `prerelease=false`, notas corrigidas e 16/16 assets íntegros.
Nenhuma nova versão, tag ou distribuição foi criada.
Cada projeto usa um environment GitHub próprio para distinguir sua identidade
OIDC:

| Projeto PyPI | Environment | Versão 1.0.1 | Publisher |
| --- | --- | --- | --- |
| `atlas-agent-core` | `pypi` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-adapters` | `pypi-adapters` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-config` | `pypi-config` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-evaluation` | `pypi-evaluation` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-framework` | `pypi-framework` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-mcp` | `pypi-mcp` | `2/2 HASH_VERIFIED` | `ACTIVE` |
| `atlas-agent-providers` | `pypi-providers` | `2/2 HASH_VERIFIED` | `ACTIVE` |

O [formulário de Pending Publisher](https://pypi.org/manage/account/publishing/)
é preenchido pela conta PyPI responsável. O primeiro upload de cada projeto
converteu seu registro pendente em publicador ativo; a interface autenticada
confirmou sete ativos e nenhum pendente. A integridade da GitHub Release
pública foi reconfirmada: tag e commit certificados, `draft=false`, 16/16
SHA-256 válidos e manifesto íntegro. Não inserir tokens
em documentação, commit, issue ou conversa.
