# Atlas Agent Framework 1.0.1 — Estado da publicação

## Decisão

**PENDING_PYPI_AUTH.** O gate técnico da versão estável está
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
- Não havia `UV_PUBLISH_TOKEN`, credenciais Twine/PyPI, `.pypirc`, secret
  do repositório ou environment PyPI configurado neste ambiente.
- Trusted Publishing tentou obter identidade OIDC, mas esta execução local
  não é um ambiente suportado para emitir o token.
- Upload: `NOT_ATTEMPTED` por falta de autenticação protegida.

## Próxima ação

Definir um canal protegido de autenticação para publicar os sete projetos:
Trusted Publishing em GitHub Actions ou token PyPI disponibilizado por um
secret/ambiente local seguro. Não inserir tokens em documentação, commit,
issue ou conversa. Após configurar o canal, conferir novamente os 14 arquivos
e os nomes no registry, fazer upload dos artefatos certificados e verificar
cada projeto e cada arquivo no PyPI. Somente depois publicar o rascunho da
GitHub Release e registrar a decisão `PUBLISHED`.
