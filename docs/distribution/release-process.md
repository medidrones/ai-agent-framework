# Processo de release

Nenhum build local publica artefatos. Publicação futura deve usar Trusted
Publishing/OIDC, sem token de longa duração no repositório.

Checklist:

1. confirmar working tree limpa e branch de release;
2. editar somente `VERSION` e executar `make sync-version`;
3. atualizar `CHANGELOG.md`, incluindo migrações e compatibilidade;
4. revisar imports públicos, wire contracts, schema de config, plugins e
   checkpoints;
5. executar `uv sync --locked` e `make quality`;
6. executar a matriz Python 3.12/3.13;
7. executar `make artifacts` e `make packaging-smoke`;
8. conferir metadata, licenças, `py.typed`, entry points e ausência de arquivos
   privados;
9. consultar o índice oficial e comprovar que todos os nomes de distribuição
   estão disponíveis ou pertencem à organização responsável;
10. produzir release notes curadas e criar o tag correspondente a `VERSION`;
11. publicar por ambiente protegido e verificar instalação do índice.

Release candidates, como `1.0.0rc1`, seguem o mesmo processo. Um release não
pode sair de working tree suja, com changelog ausente, tag divergente, smoke
test falho ou artefatos gerados fora da matriz aprovada.

O protobuf é regenerado apenas no ambiente de desenvolvimento com
`grpcio-tools`; o runtime do adapter não depende dessa ferramenta. Alterações no
`.proto` precisam incluir o código gerado atualizado e passar pelo smoke gRPC.
