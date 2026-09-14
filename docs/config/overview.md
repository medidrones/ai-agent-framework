# Configuração declarativa

A distribuição opcional `atlas-agent-config` transforma YAML, JSON ou objetos
Python em uma composição executável do Atlas. A composição manual por Python
continua sendo uma API de primeira classe e não depende deste pacote.

O fluxo público é explícito:

1. carregue `AtlasConfig` com `load_yaml`, `load_json` ou `load_config`;
2. registre factories confiáveis em `ConfigurationFactoryRegistry`;
3. injete segredos, plugins e dependências externas no
   `AtlasCompositionBuilder`;
4. construa uma `AtlasComposition` e feche-a com `async with` ou `close()`.

Para habilitar a construção do serviço usado por adapters externos, instale
`atlas-agent-config[adapters]`. O import e o uso básico do pacote não dependem
de FastAPI ou gRPC.

O schema atual é a versão inteira `1`. Campos desconhecidos, IDs vazios,
referências inválidas, factories ausentes e versões desconhecidas falham antes
da criação de componentes. Adapters e MCP são desabilitados por padrão;
ferramentas remotas MCP não são importadas sem allowlist explícita.

Consulte [schema](schema.md), [YAML e JSON](yaml.md),
[segredos](secrets.md), [factories](factories.md),
[composição](composition.md), [overrides](overrides.md) e
[segurança](security.md).
