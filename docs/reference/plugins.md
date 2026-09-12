# Referência de plugins

O namespace `atlas_agents.plugins` define a extensão opcional do Atlas por
pacotes Python independentes. Descobrir, carregar, registrar e ativar são
operações diferentes. Nenhuma delas acontece automaticamente.

## Contrato

Todo plugin herda `Plugin` e implementa:

```python
class Plugin(ABC):
    @property
    def manifest(self) -> PluginManifest: ...

    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]: ...

    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]: ...

    async def deactivate(self, context: PluginContext) -> None: ...
```

`describe()` é síncrono e deve ser livre de efeitos colaterais. Cada descritor
representa exatamente uma contribuição pela dupla `(capability, identifier)`.
`activate()` só é chamado após compatibilidade, manifesto e conflitos terem
sido validados.

## Manifesto e compatibilidade

`PluginMetadata` contém `plugin_id`, nome, versão, descrição, autor, homepage e
metadata JSON-safe. O ID canônico vem do manifesto, nunca do alias do entry
point. `PluginManifest` declara capabilities em ordem, dependências opcionais
informativas e `required_atlas_version`, validado por
`packaging.specifiers.SpecifierSet` contra a versão instalada do core.
Pré-releases seguem a decisão padrão do `packaging` para o specifier declarado;
o Atlas não força sua inclusão.

As capabilities disponíveis são `MODEL_PROVIDER`, `TOOL`, `MEMORY_STORE`,
`KNOWLEDGE_RETRIEVER`, `GUARDRAIL`, `EVALUATOR` e `OBSERVABILITY`. A capability
genérica `ADAPTER` foi reservada para uma evolução posterior: nesta versão,
todo valor contribuído possui um contrato forte e específico.

## Descoberta e carregamento

`PluginDiscovery` consulta somente o grupo `atlas_agents.plugins` por
`importlib.metadata`. O resultado contém descritores serializáveis, ordenados
por distribuição, nome e valor. A descoberta não importa módulos.

`PluginLoader.load()` aceita somente um `PluginEntryPoint` produzido pela
descoberta, chama uma factory síncrona sem argumentos exatamente uma vez e
valida que o resultado herda `Plugin`. Falhas de import ou da factory são
normalizadas sem traceback e sem mensagem original potencialmente sensível.

## Registro e ativação

`PluginRegistry` é local à instância e protege IDs duplicados. Registrar um
plugin não registra suas contribuições. `PluginManager.activate()` executa:

```text
compatibilidade → describe → validação → preflight → activate → registro
```

Contribuições de `ModelProvider`, `Tool`, `Guardrail` e `Evaluator` são
registradas somente quando seus registries foram injetados explicitamente no
manager. Memory stores, retrievers e observabilidade ficam disponíveis em
`get_contributions()` para composição explícita pelo host; não substituem
managers nem alteram um `AgentRuntime` existente.

O registro preserva a ordem das contribuições. Em falha intermediária, o
manager tenta remover as contribuições anteriores em ordem inversa e nunca
marca o plugin como ativo. Um rollback incompleto produz `PluginRollbackError`.

## Desativação

`deactivate(plugin_id)` remove contribuições gerenciadas em ordem inversa e
depois chama a limpeza do plugin com o mesmo `PluginContext` usado na ativação.
Após desativação, o plugin pode ser ativado novamente. `CancelledError` não é
convertido em erro do domínio de plugins.

## Resultados seguros

`PluginActivationResult` e `PluginInfo` contêm apenas manifestos, descritores e
estado. Configuração e objetos implementadores não são serializados. O host usa
`get_contributions()` exclusivamente durante a composição local.

O sistema não oferece ativação global, instalação de dependências, hot reload,
service locator ou sandbox.
