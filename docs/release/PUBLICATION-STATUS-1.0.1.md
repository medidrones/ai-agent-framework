# Atlas Agent Framework 1.0.1 — Estado da publicação

## Decisão

**BLOCKED_PYPI_PENDING_LIMIT.** O gate técnico da versão estável está
`READY_TO_PUBLISH` e o usuário autorizou a publicação oficial. A tag e os
assets foram preparados no GitHub, mas a GitHub Release permanece em rascunho
e nenhum pacote foi enviado ao PyPI. Não marcar como `PUBLISHED` até verificar
o registry e publicar o rascunho.

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

## PyPI

- Os sete nomes `atlas-agent-framework`, `atlas-agent-adapters`,
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
  bundle certificado sem OIDC e publica cada distribuição em um job separado,
  com environment protegido próprio. O environment `pypi` é exclusivo do core.
- Os Pending Publishers de `atlas-agent-core`, `atlas-agent-adapters` e
  `atlas-agent-config` foram registrados na conta PyPI `medicode` e conferidos
  na lista de publicadores, cada um com seu environment próprio. O PyPI recusou
  a tentativa de registrar `atlas-agent-evaluation`: esta conta não pode manter
  mais de três publicadores pendentes simultaneamente. Os outros três também
  permanecem sem registro.
- Os sete environments GitHub existem, exigem aprovação de `medidrones` e
  permitem deploy apenas em `main`. O workflow corrigido foi aceito pelo
  GitHub no commit `1b215b7ae261611130b8c045bff17f8ae993c5be`; os gates
  de Qualidade e Empacotamento desse commit passaram.
- Upload: `NOT_ATTEMPTED`. O workflow manual foi temporariamente desativado
  no GitHub (`disabled_manually`) para impedir uma publicação parcial com
  somente três dos sete Pending Publishers. A desativação é reversível e não
  altera a tag, o commit certificado ou os artefatos.

## Próxima ação

Registrar separadamente os sete Pending Publishers no PyPI, todos com owner
GitHub `medidrones`, repositório `ai-agent-framework` e workflow
`publish-pypi.yml`. Cada projeto ainda inexistente usa um environment
GitHub próprio para distinguir sua identidade OIDC:

| Projeto PyPI | Environment | Pending Publisher |
| --- | --- | --- |
| `atlas-agent-core` | `pypi` | `REGISTERED` |
| `atlas-agent-adapters` | `pypi-adapters` | `REGISTERED` |
| `atlas-agent-config` | `pypi-config` | `REGISTERED` |
| `atlas-agent-evaluation` | `pypi-evaluation` | `NOT_VERIFIED` |
| `atlas-agent-framework` | `pypi-framework` | `NOT_VERIFIED` |
| `atlas-agent-mcp` | `pypi-mcp` | `NOT_VERIFIED` |
| `atlas-agent-providers` | `pypi-providers` | `NOT_VERIFIED` |

O [formulário de Pending Publisher](https://pypi.org/manage/account/publishing/)
é preenchido pela conta PyPI responsável. Essa configuração não cria nem
reserva um projeto antes do primeiro upload. O próprio PyPI informou o limite
de três publicadores pendentes simultâneos por conta. O próximo passo depende
de uma decisão de governança: solicitar uma exceção ao PyPI ou autorizar
publicação controlada em lotes, na qual cada primeiro upload converte o
publicador pendente em ativo e libera espaço para os próximos registros.
Nenhum desses caminhos deve publicar a GitHub Release em rascunho antes da
verificação dos sete projetos e dos 14 hashes. Não inserir tokens em
documentação, commit, issue ou conversa.
