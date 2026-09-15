# Evidências técnicas da 1.0.1rc2

Este registro foi acrescentado em `main` após a certificação, sem modificar
o commit nem a tag anotada da candidata.

- RC: `1.0.1rc2`
- Tag anotada: `v1.0.1rc2`
- Commit certificado: `31ccac66c0fc2002fe908e68e40a07c95f684c72`
- Qualidade inicial: [workflow 35010263682](https://github.com/medidrones/ai-agent-framework/actions/runs/35010263682), attempt 1, `PASS` em Ubuntu/Windows 3.12/3.13
- Empacotamento inicial: [workflow 35010263815](https://github.com/medidrones/ai-agent-framework/actions/runs/35010263815), `PASS`
- Certificação da tag: [workflow 35010523479](https://github.com/medidrones/ai-agent-framework/actions/runs/35010523479), attempt 1, `PASS`
- Artefato da CI: `atlas-v1.0.1rc2`, ID `10413950548`
- SHA-256 do manifesto `SHA256SUMS`: `cffb7b2186501787bf89092acb94aff9988c7535525e0d8cbe2619d97f0c9762`
- Inventário: sete wheels, sete sdists, 15 checksums verificados
- SBOM: CycloneDX, versão `1.0.1rc2`, 79 componentes
- Segredos nos artefatos: zero findings
- Regressão certificada: 1.141 testes, zero falhas ou erros
- Status técnico: `PASS`
- Owner sign-offs: `NOT_VERIFIED`
- Decisão final: `NOT_READY`

O SBOM é armazenado no bundle como `sbom.cdx.json`; a linha correspondente
em `SHA256SUMS` usa o nome original `atlas-agent-framework.cdx.json`. O
checksum do conteúdo copiado foi verificado, sem alteração dos bytes.

Os relatórios técnicos completos estão no artefato arquivado pelo workflow.
As cinco aprovações da `1.0.1rc1` não substituem decisões humanas referentes
à nova fonte certificada. Não há tag estável `v1.0.1` nem publicação no PyPI.
