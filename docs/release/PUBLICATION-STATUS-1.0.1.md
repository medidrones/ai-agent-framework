# Atlas Agent Framework 1.0.1 — Estado da publicação

## Decisão

**PENDING_PYPI_PUBLISHERS.** O gate técnico da versão estável está
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
- O Pending Publisher de `atlas-agent-core` foi registrado na conta PyPI
  `medicode` e conferido na lista de publicadores. O PyPI recusou o segundo
  projeto com a mesma identidade OIDC, informando que ela já estava registrada
  para outro projeto pendente. Os seis restantes exigem environments distintos.
- Upload: `NOT_ATTEMPTED` até os sete registros estarem concluídos.

## Próxima ação

Registrar separadamente os sete Pending Publishers no PyPI, todos com owner
GitHub `medidrones`, repositório `ai-agent-framework` e workflow
`publish-pypi.yml`. Cada projeto ainda inexistente usa um environment
GitHub próprio para distinguir sua identidade OIDC:

| Projeto PyPI | Environment | Pending Publisher |
| --- | --- | --- |
| `atlas-agent-core` | `pypi` | `REGISTERED` |
| `atlas-agent-adapters` | `pypi-adapters` | `NOT_VERIFIED` |
| `atlas-agent-config` | `pypi-config` | `NOT_VERIFIED` |
| `atlas-agent-evaluation` | `pypi-evaluation` | `NOT_VERIFIED` |
| `atlas-agent-framework` | `pypi-framework` | `NOT_VERIFIED` |
| `atlas-agent-mcp` | `pypi-mcp` | `NOT_VERIFIED` |
| `atlas-agent-providers` | `pypi-providers` | `NOT_VERIFIED` |

O [formulário de Pending Publisher](https://pypi.org/manage/account/publishing/)
é preenchido pela conta PyPI responsável. Essa configuração não cria nem
reserva um projeto antes do primeiro upload. Após confirmação dos sete
registros, executar manualmente o workflow em `main`, aprovar os sete jobs nos
environments respectivos, conferir os 14 hashes no PyPI e somente então publicar o
rascunho da GitHub Release. Não inserir tokens em documentação, commit, issue
ou conversa.
