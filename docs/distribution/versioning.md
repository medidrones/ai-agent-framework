# Versionamento

O Atlas adota SemVer 2.0.0 como política de compatibilidade e PEP 440 como
formato normativo dos artefatos Python. Pré-releases usam formas como
`1.0.0a1`, `1.0.0b1` e `1.0.0rc1`.

Todas as distribuições são lançadas em lockstep. A única fonte editável é o
arquivo `VERSION`; `scripts/sync_versions.py` valida PEP 440, gera os módulos de
versão de cada wheel e sincroniza constraints internas. Não edite os módulos
`version.py` ou `_version.py` manualmente.

Constraints internas usam compatible release no minor atual, como
`atlas-agent-core~=0.1.0`. Assim, o conjunto publicado aceita correções do mesmo
minor e não presume compatibilidade cross-minor sem validação.

- PATCH: correção compatível, hardening ou refatoração interna;
- MINOR: API compatível, provider/adapter opcional ou novo schema coexistente;
- MAJOR: remoção pública, quebra de plugin/checkpoint/config ou wire contract.

Antes de 1.0, mudanças incompatíveis ainda precisam de changelog e migração,
mas podem ocorrer em um minor. Depois de 1.0, quebras estáveis exigem major.
Um único tag `vMAJOR.MINOR.PATCH` identifica o release lockstep.
