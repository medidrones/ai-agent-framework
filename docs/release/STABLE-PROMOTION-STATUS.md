# Atlas Agent Framework — Gate de promoção estável 1.0.1

## Estado

**IN_PROGRESS.** A candidata `1.0.1rc2` está certificada e aprovada por cinco
owner sign-offs. A nova promoção estável exige certificação específica dos
artefatos `1.0.1` antes de qualquer decisão `READY_TO_PUBLISH`.

## Fonte congelada

- RC: `1.0.1rc2`
- Tag anotada: `v1.0.1rc2`
- Commit certificado: `31ccac66c0fc2002fe908e68e40a07c95f684c72`
- Certificação: [workflow 35010523479](https://github.com/medidrones/ai-agent-framework/actions/runs/35010523479), attempt 1, `PASS`
- Owner sign-offs: cinco `PASS` de Jorge Medina,
  [registrados individualmente](evidence/1.0.1rc2/SIGN-OFF-STATUS.md)
- P0/P1 abertas: `0/0` no gate de sign-offs
- Integridade do RC: `VERIFIED`, 14 artefatos, 15 checksums

## Delta autorizado

- `1.0.1rc2 → 1.0.1` em versões e restrições internas lockstep;
- documentação, changelog e metadados de release;
- novos artefatos, checksums e SBOM para `1.0.1`.

São proibidos mudanças funcionais, API/contratos, dependências externas,
arquitetura, política de segurança, workflows e desativação de testes.

O [relatório da tentativa anterior](history/STABLE-PROMOTION-STATUS-1.0.1rc1.md)
permanece preservado. Este documento será atualizado com resultados locais e
remotos do novo gate. Não há tag estável, GitHub Release ou envio ao PyPI.
