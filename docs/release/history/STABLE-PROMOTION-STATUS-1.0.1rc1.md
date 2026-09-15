# Atlas Agent Framework — Gate de promoção estável 1.0.1

## Origem certificada

| Campo | Valor |
| --- | --- |
| RC | `1.0.1rc1` |
| Tag | `v1.0.1rc1` |
| Commit certificado | `16d1c4d26868cec65ca9385bc76f9e9db8f81d97` |
| Workflow de certificação | [34896013098](https://github.com/medidrones/ai-agent-framework/actions/runs/34896013098) |
| Owner sign-offs | `PASS`, Jorge Medina nos cinco papéis |
| Integridade do RC | `VERIFIED`, 14 artefatos e 15 checksums |
| Alterações materiais após o RC | `NONE` |
| P0/P1 abertas | `0/0` |

As aprovações formais estão em
[`docs/release/evidence/1.0.1rc1/`](../evidence/1.0.1rc1/README.md).
As tags `v1.0.0` e `v1.0.1rc1` permanecem imutáveis.

## Delta de promoção autorizado

- remoção do sufixo `rc1` em `VERSION` e nos sete módulos de versão;
- atualização lockstep das restrições internas dos sete pacotes;
- changelog, README, compatibilidade, notas e evidências de release;
- novos wheels, sdists, checksums e SBOM específicos de `1.0.1`.

O comparador dos wheels encontrou **zero diferenças funcionais em 221 membros
de payload** após excluir os módulos de versão e a metadata gerada. Para as
sete distribuições, `Name`, `Requires-Python` e `Requires-Dist` coincidiram
após normalizar apenas `1.0.1rc1 → 1.0.1`. Não houve mudança em código de
runtime, API, dependências externas, arquitetura, schemas, wire contracts,
políticas de segurança ou testes.

## Certificação local dos artefatos estáveis

| Verificação | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| Ruff lint e formato | PASS |
| mypy | PASS — 332 arquivos |
| Regressão | PASS — 1.141 testes, 93% de cobertura |
| Build | PASS — sete wheels e sete sdists |
| Metadata, licença, `py.typed` e entry points | PASS |
| Reprodutibilidade de metadata e manifestos | PASS |
| Instalação limpa, sem editable | PASS — core, base e full |
| Namespace, extras e imports opcionais | PASS |
| Auditoria de arquitetura e API | PASS |
| Bandit | PASS — zero findings |
| pip-audit | PASS — nenhuma vulnerabilidade conhecida |
| Scanner de segredos | PASS — zero findings em 14 artefatos |
| SHA-256 | PASS — 15 entradas verificadas |
| SBOM CycloneDX | PASS — versão `1.0.1`, 79 componentes |
| Exemplos .NET REST e gRPC | PASS — zero erros e avisos |
| Empacotamento remoto do commit estável | PASS — [workflow 35008774134](https://github.com/medidrones/ai-agent-framework/actions/runs/35008774134) |
| Qualidade remota do commit estável | FAIL na primeira execução do Windows 3.12; PASS na repetição seletiva — [workflow 35008774072](https://github.com/medidrones/ai-agent-framework/actions/runs/35008774072) |
| Bundle remoto | PASS — 14 artefatos, 15 checksums, SBOM `1.0.1`, zero segredos e zero ciclos |
| Delta do payload remoto | PASS — zero diferenças funcionais em 221 membros |

Os artefatos e relatórios desta etapa estão locais em `dist/` e
`reports/release/`. Os artefatos antigos foram preservados em
`release/archived-dist-before-1.0.1/`. Nenhum pacote foi enviado ao PyPI.

## Finding de qualidade

Na primeira execução do commit estável
`10182b9a8003258c845a35b955f547fdcdee02bf`, o runner Windows 3.12
registrou 1 falha em 1.141 testes:
`test_stream_timeout_covers_selection_before_provider_invocation` esperava
uma chamada ao catálogo do provider após configurar um timeout total de apenas
`0.001` segundo, mas o deadline venceu antes da invocação. A repetição
seletiva passou sobre a mesma fonte, sem alteração de código. Isso indica uma
asserção temporal sensível à carga, não uma diferença funcional entre RC e
versão estável.

A repetição verde não apaga a falha da execução bloqueante inicial. Uma
correção do teste alteraria a fonte certificada e não pertence ao delta de
promoção autorizado; exigiria nova candidata e recertificação antes de
publicar a versão estável.

## Decisão final

```text
STABLE PROMOTION       FAIL
SOURCE RC              1.0.1rc1
TARGET                 1.0.1
RC COMMIT              16d1c4d26868cec65ca9385bc76f9e9db8f81d97
OWNER SIGN-OFFS        PASS
P0/P1 OPEN             0/0
PROMOTION DELTA        VERIFIED
LOCAL ARTIFACTS        VERIFIED
REMOTE ARTIFACTS       VERIFIED
REMOTE REGRESSION      NOT_VERIFIED — falha temporal na primeira execução

FINAL DECISION         NOT_READY_TO_PUBLISH
```

Não foi criada a tag `v1.0.1` nem uma GitHub Release para esta fonte. Os
artefatos não foram enviados ao PyPI. O próximo ciclo deve estabilizar o teste
em uma nova candidata, certificar essa candidata imutável e repetir a promoção
sem alteração funcional. Publicação no PyPI continua sujeita a autorização
explícita separada e autenticação protegida.
