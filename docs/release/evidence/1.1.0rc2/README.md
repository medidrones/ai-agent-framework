# Evidências técnicas da 1.1.0rc2

Este registro foi acrescentado em `main` após a certificação, sem modificar o
commit nem a tag anotada da candidata.

- RC: `1.1.0rc2`
- Tag anotada: `v1.1.0rc2`
- Commit certificado: `fd91bad8d6919a46504ba7fa45fee02fc9e21d52`
- Qualidade pós-merge: [workflow 38974280192](https://github.com/medidrones/ai-agent-framework/actions/runs/38974280192), `PASS`
- Empacotamento pós-merge: [workflow 38974280194](https://github.com/medidrones/ai-agent-framework/actions/runs/38974280194), `PASS`
- Certificação da tag: [workflow 38974750546](https://github.com/medidrones/ai-agent-framework/actions/runs/38974750546), `PASS`
- Artefato da CI: `atlas-v1.1.0rc2`, ID `12078093020`
- Digest do artefato da CI: `sha256:aa760d713b031c032760bc0de0fa704c21f078d2df6566d7f60fc1b3162c59b3`
- SHA-256 do manifesto `SHA256SUMS`: `8f2f087027aaaaeb77ba9806e59aa82b8fb6334a192e29024a4495c4cfdba9d3`
- Inventário: sete wheels, sete sdists e 15 checksums verificados
- SBOM: CycloneDX 1.6, versão `1.1.0rc2`, 84 componentes
- Segredos nos artefatos: zero findings
- Dependências vulneráveis conhecidas: zero findings
- Regressão certificada: 1.456 testes, zero falhas, erros ou skips
- Cobertura certificada: 94,49% de linhas e 83,32% de branches
- Status técnico: `PASS`
- Owner sign-offs: `PASS` — cinco decisões distintas de Jorge Medina,
  registradas em [SIGN-OFF-STATUS.md](SIGN-OFF-STATUS.md)
- Decisão final: `READY_FOR_STABLE`

O SBOM é armazenado no bundle como `sbom.cdx.json`; a linha correspondente
em `SHA256SUMS` usa o nome original `atlas-agent-framework.cdx.json`. Os
checksums do conteúdo foram verificados pelo workflow.

Os relatórios técnicos completos estão no artefato arquivado pelo workflow.
O bundle original registra `NOT_VERIFIED` porque foi gerado antes da decisão
humana; estes registros versionados documentam o gate administrativo
posterior. Não há tag estável `v1.1.0` nem publicação no PyPI.
