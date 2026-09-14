# Atlas Agent Framework — Correção do nome público no RC4

## Problema confirmado

O nome `atlas-agent` no PyPI pertence ao projeto Feng Lab e não pode ser usado
pelo Atlas Agent Framework. A tentativa de publicação foi interrompida antes de
qualquer upload ao registry.

## Solução

| Item | Valor |
| --- | --- |
| Versão | `1.0.0rc4` |
| Novo nome público | `atlas-agent-framework` |
| Namespace Python | `atlas_agent` — preservado |
| Pacotes auxiliares | seis nomes preservados |
| Alteração funcional | nenhuma |
| Alteração de API | nenhuma |
| Alteração de dependência externa | nenhuma |

O identificador privado do projeto-raiz passou a ser `atlas-agent-workspace`
com versão fixa `0.0.0`. Isso mantém a raiz virtual fora do build e elimina a
obtenção de versão dinâmica durante a resolução do workspace.

## Cobertura da correção

- metadata do meta-package;
- fonte workspace do uv e lockfile;
- comandos de build;
- inspeção e reprodutibilidade dos artefatos;
- instalação limpa do extra `full`;
- política arquitetural e de distribuição;
- teste que proíbe a reintrodução do nome ocupado;
- documentação de instalação e release.

## Evidências locais

```text
VERSION                1.0.0rc4
PUBLIC META-PACKAGE    atlas-agent-framework
PYTHON NAMESPACE       atlas_agent
PYPI NAME CHECK        PASS
LINT                    PASS
FORMAT                  PASS
TYPING                  PASS
TESTS                   PASS — 1.140
COVERAGE                93%
ARTIFACTS               14 VERIFIED
REPRODUCIBILITY         PASS
CLEAN INSTALL           PASS
ARTIFACT SECRET SCAN    PASS
DEPENDENCY AUDIT        PASS
SBOM                    79 COMPONENTS
CHECKSUMS               15
DOTNET EXAMPLES         PASS

FINAL DECISION          READY_FOR_RC
PYPI PUBLICATION        NOT_AUTHORIZED_FOR_RC
```

## Limitações

- A disponibilidade de nomes no PyPI não representa reserva e deve ser
  reconfirmada imediatamente antes da publicação.
- A tag e a GitHub Release `v1.0.0` existentes não foram removidas nem
  reescritas.
- A tag anotada `v1.0.0rc4` foi publicada e permanece imutável.
- Os gates de qualidade, segurança e matriz remota passaram, mas a certificação
  final falhou porque o montador de evidências ainda procurava
  `atlas_agent-*`. A correção segue no `1.0.0rc5`.
